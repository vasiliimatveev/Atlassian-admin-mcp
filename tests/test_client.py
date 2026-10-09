import asyncio

import httpx
import pytest

from jira_dc_analyst.client import AnalystError
from jira_dc_analyst.config import DEFAULT_SR_PATH

from .conftest import BASE


async def test_sr_action_builds_query_and_drops_empty_params(jira, client_factory):
    jira.sr("list_workflows", [{"name": "WF"}])
    client = client_factory()
    assert await client.sr_action("list_workflows", search="", project=None, n=5) == [
        {"name": "WF"}
    ]
    req = jira.requests[0]
    assert req.url.path == DEFAULT_SR_PATH
    assert dict(req.url.params) == {"action": "list_workflows", "n": "5"}
    assert req.headers["Authorization"] == "Bearer test-token"
    assert req.headers["Accept"] == "application/json"


async def test_basic_auth_when_no_token(jira, client_factory):
    jira.add("/rest/api/2/myself", {})
    client = client_factory(personal_token=None, username="u", password="p")
    await client.rest_get("/rest/api/2/myself")
    assert jira.requests[0].headers["Authorization"].startswith("Basic ")


async def test_context_path_in_base_url_is_kept(jira, client_factory):
    jira.add("/jira/rest/api/2/serverInfo", {"v": 1})
    client = client_factory(url=BASE + "/jira")
    assert await client.rest_get("/rest/api/2/serverInfo") == {"v": 1}


async def test_http_error_carries_status_body_and_url(jira, client_factory):
    jira.add("/rest/x", {"errorMessages": ["nope"]}, status=403)
    with pytest.raises(AnalystError) as info:
        await client_factory().rest_get("/rest/x")
    assert info.value.status == 403
    assert "nope" in info.value.body
    assert info.value.url == BASE + "/rest/x"


async def test_html_instead_of_json_is_reported(jira, client_factory):
    jira.add("/rest/x", content=b"<!DOCTYPE html><html>login</html>")
    with pytest.raises(AnalystError, match="HTML"):
        await client_factory().rest_get("/rest/x")


async def test_empty_body_is_empty_dict(jira, client_factory):
    jira.add("/rest/x", content=b"")
    assert await client_factory().rest_get("/rest/x") == {}


async def test_redirects_are_not_followed(jira, client_factory):
    jira.add("/rest/x", content=b"", status=302, headers={"Location": "https://sso.example.com/"})
    with pytest.raises(AnalystError) as info:
        await client_factory().rest_get("/rest/x")
    assert info.value.status == 302
    assert len(jira.requests) == 1


@pytest.mark.parametrize("path", ["/rest/../admin", "/rest/./x", "/rest/%2e%2e/x", "rest/x"])
async def test_dot_segments_and_relative_paths_are_rejected(jira, client_factory, path):
    with pytest.raises(AnalystError):
        await client_factory().rest_get(path)
    assert jira.requests == []


# ---------------------------------------------------------------- caching


async def test_cache_serves_repeat_calls(jira, client_factory):
    jira.add("/rest/x", {"a": 1})
    client = client_factory()
    assert await client.rest_get("/rest/x", q=1) == {"a": 1}
    assert await client.rest_get("/rest/x", q=1) == {"a": 1}
    assert len(jira.requests) == 1
    assert client.cache_stats()["hits"] == 1
    await client.rest_get("/rest/x", q=2)  # different params → different key
    assert len(jira.requests) == 2


async def test_cached_results_are_independent_copies(jira, client_factory):
    jira.add("/rest/x", [{"a": 1}])
    client = client_factory()
    first = await client.rest_get("/rest/x")
    first[0]["a"] = "mutated"
    assert await client.rest_get("/rest/x") == [{"a": 1}]


async def test_cache_false_and_ttl_zero_bypass_cache(jira, client_factory):
    jira.add("/rest/x", {})
    client = client_factory()
    await client.rest_get("/rest/x", cache=False)
    await client.rest_get("/rest/x", cache=False)
    assert len(jira.requests) == 2
    uncached = client_factory(cache_ttl=0)
    await uncached.rest_get("/rest/x")
    await uncached.rest_get("/rest/x")
    assert len(jira.requests) == 4
    assert uncached.cache_stats() == {"enabled": False}


async def test_errors_are_not_cached(jira, client_factory):
    jira.add("/rest/x", {}, status=500)
    client = client_factory()
    for _ in range(2):
        with pytest.raises(AnalystError):
            await client.rest_get("/rest/x")
    assert len(jira.requests) == 2


async def test_concurrent_identical_requests_are_deduplicated(jira, client_factory):
    gate = asyncio.Event()

    async def slow(request: httpx.Request) -> httpx.Response:
        jira.requests.append(request)
        await gate.wait()
        return httpx.Response(200, json={"ok": True})

    client = client_factory()
    client._http._transport = httpx.MockTransport(slow)  # async handler
    tasks = [asyncio.create_task(client.rest_get("/rest/x")) for _ in range(5)]
    await asyncio.sleep(0.05)
    gate.set()
    assert await asyncio.gather(*tasks) == [{"ok": True}] * 5
    assert len(jira.requests) == 1


async def test_failed_shared_request_propagates_to_all_waiters(jira, client_factory):
    gate = asyncio.Event()

    async def failing(request: httpx.Request) -> httpx.Response:
        jira.requests.append(request)
        await gate.wait()
        return httpx.Response(500, json={})

    client = client_factory()
    client._http._transport = httpx.MockTransport(failing)
    tasks = [asyncio.create_task(client.rest_get("/rest/x")) for _ in range(3)]
    await asyncio.sleep(0.05)
    gate.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert all(isinstance(r, AnalystError) and r.status == 500 for r in results)
    assert len(jira.requests) == 1


async def test_concurrency_is_capped(jira, client_factory):
    active = peak = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(200, json={})

    client = client_factory(max_concurrency=2)
    client._http._transport = httpx.MockTransport(handler)
    await asyncio.gather(*(client.rest_get("/rest/x", i=i) for i in range(8)))
    assert peak == 2


# ---------------------------------------------------------------- retries


async def test_retries_transient_statuses_then_succeeds(jira, client_factory, monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    calls = iter([503, 429, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        jira.requests.append(request)
        status = next(calls)
        return httpx.Response(status, json={"n": len(jira.requests)})

    client = client_factory(retries=2)
    client._http._transport = httpx.MockTransport(handler)
    assert await client.rest_get("/rest/x") == {"n": 3}


async def test_gives_up_after_retries(jira, client_factory, monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    jira.add("/rest/x", {}, status=503)
    with pytest.raises(AnalystError) as info:
        await client_factory(retries=2).rest_get("/rest/x")
    assert info.value.status == 503
    assert len(jira.requests) == 3


async def test_does_not_retry_client_errors(jira, client_factory):
    jira.add("/rest/x", {}, status=404)
    with pytest.raises(AnalystError):
        await client_factory(retries=3).rest_get("/rest/x")
    assert len(jira.requests) == 1


async def test_transport_errors_are_retried_and_wrapped(jira, client_factory, monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)

    def boom(request: httpx.Request) -> httpx.Response:
        jira.requests.append(request)
        raise httpx.ConnectError("refused", request=request)

    client = client_factory(retries=1)
    client._http._transport = httpx.MockTransport(boom)
    with pytest.raises(AnalystError, match="transport error") as info:
        await client.rest_get("/rest/x")
    assert info.value.status is None
    assert len(jira.requests) == 2


def test_backoff_honours_retry_after_with_cap():
    from jira_dc_analyst.client import AnalystClient

    assert AnalystClient._backoff(0, "3") == 3.0
    assert AnalystClient._backoff(0, "999") == 10.0
    assert AnalystClient._backoff(2, None) == 2.0
    assert AnalystClient._backoff(1, "Wed, 21 Oct 2026 07:28:00 GMT") == 1.0


async def _no_sleep(_seconds: float) -> None:
    return None


# ---------------------------------------------------------------- downloads


async def test_fetch_bytes_relative_url(jira, client_factory):
    jira.add("/secure/attachment/1/a.txt", content=b"hello")
    assert await client_factory().fetch_bytes("/secure/attachment/1/a.txt") == b"hello"


async def test_fetch_bytes_never_sends_credentials_to_foreign_host(jira, client_factory):
    jira.add("/secure/attachment/1/a.txt", content=b"ok")
    data = await client_factory().fetch_bytes("https://evil.example.net/secure/attachment/1/a.txt")
    assert data == b"ok"
    assert jira.requests[0].url.host == "jira.example.com"


async def test_fetch_bytes_rejects_bad_urls(jira, client_factory):
    client = client_factory()
    for url in ("", "file:///etc/passwd", "/secure/../../etc"):
        with pytest.raises(AnalystError):
            await client.fetch_bytes(url)
    assert jira.requests == []


async def test_fetch_bytes_limit_by_content_length(jira, client_factory):
    jira.add("/f", content=b"x" * 100)
    with pytest.raises(AnalystError) as info:
        await client_factory().fetch_bytes("/f", max_bytes=10)
    assert info.value.status == 413


async def test_fetch_bytes_limit_while_streaming(jira, client_factory):
    async def body():
        for _ in range(10):
            yield b"x" * 10

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body())  # no Content-Length

    client = client_factory()
    client._http._transport = httpx.MockTransport(handler)
    with pytest.raises(AnalystError, match="exceeds limit"):
        await client.fetch_bytes("/f", max_bytes=25)
    assert await client.fetch_bytes("/f", max_bytes=1000) == b"x" * 100


async def test_fetch_bytes_http_error(jira, client_factory):
    with pytest.raises(AnalystError) as info:
        await client_factory().fetch_bytes("/missing")
    assert info.value.status == 404


async def test_fetch_bytes_relative_url_respects_context_path(jira, client_factory):
    jira.add("/jira/secure/thumbnail/1/t.png", content=b"png")
    client = client_factory(url=BASE + "/jira")
    assert await client.fetch_bytes("/secure/thumbnail/1/t.png") == b"png"
    jira.add("/jira/secure/attachment/2/a.txt", content=b"abs")
    assert (
        await client.fetch_bytes("https://public.example.org/jira/secure/attachment/2/a.txt")
        == b"abs"
    )
