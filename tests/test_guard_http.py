"""Guard over real streamable HTTP: header-driven guard, per-call isolation, cache."""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time

import httpx
import pytest
import uvicorn
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from atlassian_admin_mcp.server import create_server

from .conftest import FakeJira, make_settings
from .test_guard import install_search


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def http_server():
    jira = FakeJira()
    install_search(jira, visible={"SOS-1": "100", "ABC-2": "200"})
    jira.add("/rest/api/2/issue/SOS-1/votes", {"votes": 1})
    jira.add("/rest/api/2/issue/ABC-2/votes", {"votes": 2})

    def search_by_guard(request: httpx.Request) -> httpx.Response:
        # Honour the guard part of the JQL too, so different headers see different issues.
        jql = request.url.params["jql"]
        allowed = {"project = SOS": {"SOS-1": "100"}, "project = ABC": {"ABC-2": "200"}}
        guard = jql[1 : jql.index(")")]
        visible = allowed.get(guard, {})
        ref = jql.rsplit("(", 1)[1].rstrip(")")
        issues = [{"id": i, "key": k} for k, i in visible.items() if ref in (k, i)]
        return httpx.Response(200, json={"issues": issues})

    jira.add_handler("/rest/api/2/search", search_by_guard)

    settings = make_settings(guard_header="x-jira-guard-jql", toolsets="default")
    app = create_server(settings, transport=httpx.MockTransport(jira)).http_app()
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started
    yield f"http://127.0.0.1:{port}/mcp", jira
    server.should_exit = True
    thread.join(timeout=5)


async def _call(url: str, headers: dict[str, str] | None, key: str):
    async with Client(StreamableHttpTransport(url, headers=headers)) as c:
        return await c.call_tool("jira_get_issue_votes", {"issue_key": key}, raise_on_error=False)


async def test_header_guard_end_to_end(http_server):
    url, jira = http_server

    ok = await _call(url, {"x-jira-guard-jql": "project = SOS"}, "SOS-1")
    assert not ok.is_error
    assert json.loads(ok.content[0].text) == {"votes": 1}

    # Same server, same (now cached) issue, different caller guard → denied.
    other = await _call(url, {"x-jira-guard-jql": "project = ABC"}, "SOS-1")
    assert other.is_error
    assert json.loads(other.content[0].text)["kind"] == "guard_denied"

    missing = await _call(url, None, "SOS-1")
    assert missing.is_error
    assert "missing" in json.loads(missing.content[0].text)["error"]

    spoof = await _call(
        url, {"x-jira-guard-jql": "project = SOS", "X-Atlassian-Jira-Url": "http://evil"}, "SOS-1"
    )
    assert spoof.is_error

    votes_calls = [r for r in jira.requests if r.url.path.endswith("/votes")]
    assert len(votes_calls) == 1  # only the first, allowed call reached Jira


async def test_concurrent_callers_do_not_share_guard_state(http_server):
    url, _ = http_server
    results = await asyncio.gather(
        *[
            _call(url, {"x-jira-guard-jql": g}, k)
            for g, k in [("project = SOS", "SOS-1"), ("project = ABC", "SOS-1")] * 5
        ]
    )
    assert [r.is_error for r in results] == [False, True] * 5
