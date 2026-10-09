"""Issue guard: every finding from the mcp-guard audit has a test here."""

from __future__ import annotations

import json
import logging
import re

import httpx
import pytest

from atlassian_admin_mcp.guard import CURRENT, GUARDED_TOOLS, CallGuard
from atlassian_admin_mcp.jql import GuardDenied

from .conftest import BASE, payload

# Issues visible under guard "project = SOS" in the fake Jira.
VISIBLE = {"SOS-1": "100", "SOS-2": "101"}
ALL_ISSUES = {**VISIBLE, "ABC-2": "200"}


def install_search(jira, visible=VISIBLE):
    """Fake /rest/api/2/search that honours ``issuekey in (...)`` and the guard."""

    def search(request: httpx.Request) -> httpx.Response:
        jql = request.url.params["jql"]
        refs = re.search(r"issuekey in \(([^)]*)\)$", jql).group(1).split(", ")
        issues = []
        for ref in refs:
            for key, issue_id in visible.items():
                if ref.upper() in (key, issue_id):
                    issues.append({"id": issue_id, "key": key})
        return httpx.Response(200, json={"issues": issues, "total": len(issues)})

    jira.add_handler("/rest/api/2/search", search)


def searches(jira) -> list[str]:
    return [r.url.params["jql"] for r in jira.requests if r.url.path == "/rest/api/2/search"]


def guarded(mcp_client, **kw):
    return mcp_client(guard_jql="project = SOS", **kw)


async def denied(c, tool, args):
    result = await c.call_tool(tool, args, raise_on_error=False)
    assert result.is_error, result.content[0].text
    body = json.loads(result.content[0].text)
    assert body["kind"] == "guard_denied", body
    return body


# ---------------------------------------------------------------- exposure


async def test_only_jql_confinable_tools_are_exposed(mcp_client):
    async with guarded(mcp_client, toolsets="all") as c:
        names = {t.name for t in await c.list_tools()}
    assert names == set(GUARDED_TOOLS) | {"jira_admin_status"}


async def test_groovy_endpoint_is_never_called_under_guard(jira, client_factory):
    client = client_factory(guard_jql="project = SOS")
    token = CURRENT.set(CallGuard(jql="project = SOS"))
    try:
        with pytest.raises(GuardDenied):
            await client.sr_action("list_workflows")
    finally:
        CURRENT.reset(token)
    assert jira.requests == []


async def test_unlisted_endpoints_are_denied(jira, client_factory):
    client = client_factory(guard_jql="project = SOS")
    token = CURRENT.set(CallGuard(jql="project = SOS"))
    try:
        for path in (
            "/rest/api/2/search",
            "/rest/api/2/issue/SOS-1/comment",
            "/rest/api/2/issue/createmeta",
            "/rest/api/2/project/SOS/properties",
            "/rest/auditing/1.0/events",
        ):
            with pytest.raises(GuardDenied):
                await client.rest_get(path)
    finally:
        CURRENT.reset(token)
    assert jira.requests == []


async def test_outside_a_tool_call_only_myself_and_server_info(jira, client_factory):
    jira.add("/rest/api/2/myself", {"name": "svc"})
    jira.add("/rest/api/2/serverInfo", {})
    client = client_factory(guard_jql="project = SOS")
    assert await client.rest_get("/rest/api/2/myself") == {"name": "svc"}
    await client.rest_get("/rest/api/2/serverInfo")
    with pytest.raises(GuardDenied):
        await client.rest_get("/rest/api/2/issue/SOS-1/votes")


# ---------------------------------------------------------------- issue references


async def test_visible_issue_is_checked_then_served(jira, mcp_client):
    install_search(jira)
    jira.add("/rest/api/2/issue/SOS-1/votes", {"votes": 3})
    async with guarded(mcp_client) as c:
        result = await c.call_tool("jira_get_issue_votes", {"issue_key": "SOS-1"})
    assert payload(result) == {"votes": 3}
    assert searches(jira) == ["(project = SOS) AND issuekey in (SOS-1)"]
    params = next(r for r in jira.requests if r.url.path == "/rest/api/2/search").url.params
    assert params["validateQuery"] == "strict"


async def test_hidden_issue_is_denied_without_touching_it(jira, mcp_client):
    install_search(jira)
    async with guarded(mcp_client) as c:
        await denied(c, "jira_get_issue_votes", {"issue_key": "ABC-2"})
    assert [r.url.path for r in jira.requests] == ["/rest/api/2/search"]


@pytest.mark.parametrize("key", ["abc-2", "Abc-2", "aBc-2"])
async def test_lowercase_keys_cannot_bypass(jira, mcp_client, key):
    """Audit finding (critical): Jira DC resolves keys case-insensitively."""
    install_search(jira)
    async with guarded(mcp_client) as c:
        await denied(c, "jira_get_issue_votes", {"issue_key": key})
    assert searches(jira) == ["(project = SOS) AND issuekey in (ABC-2)"]
    assert all(r.url.path == "/rest/api/2/search" for r in jira.requests)


@pytest.mark.parametrize("key", ["ABC%2D2", "abc%2d2", "SOS%2D1"])
async def test_percent_encoded_keys_are_denied_outright(jira, mcp_client, key):
    """A '%' in an argument is sent as %25 and would be decoded by Jira — refuse."""
    install_search(jira)
    async with guarded(mcp_client) as c:
        await denied(c, "jira_get_issue_votes", {"issue_key": key})
    assert jira.requests == []


async def test_lowercase_visible_key_still_works(jira, mcp_client):
    install_search(jira)
    jira.add_handler(
        "/rest/api/2/issue/sos-1/votes", lambda r: httpx.Response(200, json={"votes": 1})
    )
    async with guarded(mcp_client) as c:
        assert payload(await c.call_tool("jira_get_issue_votes", {"issue_key": "sos-1"}))


@pytest.mark.parametrize(
    "key", ["SOS-1;x", "7/../../api/2/search", "SOS-1\\..", "SOS-1 OR project = ABC", "%2553OS-1"]
)
async def test_path_tricks_are_denied(jira, mcp_client, key):
    """Audit finding (high): '..', ';', '\\' and encoded '/' in ids."""
    install_search(jira)
    async with guarded(mcp_client) as c:
        result = await c.call_tool("jira_get_issue_votes", {"issue_key": key}, raise_on_error=False)
    assert result.is_error
    assert json.loads(result.content[0].text)["kind"] in ("guard_denied", "invalid_argument")
    assert all(r.url.path == "/rest/api/2/search" for r in jira.requests)


async def test_numeric_issue_ids_are_checked(jira, mcp_client):
    """Audit finding: numeric ids must be recognised, not only keys."""
    install_search(jira)
    jira.add("/rest/dev-status/1.0/issue/summary", {"summary": {}})
    async with guarded(mcp_client, toolsets="all") as c:
        await denied(c, "jira_get_issue_dev_summary", {"issue_id": "200"})
        await c.call_tool("jira_get_issue_dev_summary", {"issue_id": "100"})
    assert searches(jira) == [
        "(project = SOS) AND issuekey in (200)",
        "(project = SOS) AND issuekey in (100)",
    ]


async def test_key_resolution_then_numeric_id_needs_one_check(jira, mcp_client):
    install_search(jira)
    jira.add("/rest/api/2/issue/SOS-2", {"id": "101"})
    jira.add("/rest/dev-status/1.0/issue/summary", {"summary": {}})
    async with guarded(mcp_client, toolsets="all") as c:
        await c.call_tool("jira_get_issue_dev_summary", {"issue_id": "SOS-2"})
    assert searches(jira) == ["(project = SOS) AND issuekey in (SOS-2)"]


async def test_failed_check_denies(jira, mcp_client):
    jira.add("/rest/api/2/search", {"errorMessages": ["bad JQL"]}, status=400)
    async with guarded(mcp_client) as c:
        body = await denied(c, "jira_get_issue_votes", {"issue_key": "SOS-1"})
    assert "guard check failed" in body["error"]


async def test_redirect_of_a_checked_request_is_not_returned(jira, mcp_client):
    """Audit finding: Jira redirecting a verified request elsewhere."""
    install_search(jira)
    jira.add(
        "/rest/api/2/issue/SOS-1/votes",
        content=b"",
        status=302,
        headers={"Location": f"{BASE}/rest/api/2/issue/ABC-2/votes"},
    )
    async with guarded(mcp_client) as c:
        result = await c.call_tool(
            "jira_get_issue_votes", {"issue_key": "SOS-1"}, raise_on_error=False
        )
    assert result.is_error
    assert "/rest/api/2/issue/ABC-2/votes" not in [r.url.path for r in jira.requests]


async def test_jeti_and_branches_require_an_issue(jira, mcp_client):
    install_search(jira)
    async with guarded(mcp_client, toolsets="all") as c:
        await denied(c, "jira_search_jeti_audit_log", {})
        await denied(c, "jira_get_jeti_audit_count", {"recipient": "a@b.c"})
        await denied(c, "jira_list_gij_issue_branches", {})
    assert jira.requests == []


# ---------------------------------------------------------------- JQL splicing


async def test_sla_search_jql_is_wrapped(jira, mcp_client):
    jira.add("/rest/sla/1.0/search", {"issues": []})
    async with guarded(mcp_client, toolsets="all") as c:
        await c.call_tool("jira_search_sla_status", {"jql": "status = Open ORDER BY created DESC"})
    assert jira.requests[0].url.params["jql"] == (
        "(project = SOS) AND (status = Open) ORDER BY created DESC"
    )


async def test_time_in_status_jql_is_wrapped(jira, mcp_client):
    jira.add("/rest/tis/report/1.0/api/list2", {"rows": []})
    async with guarded(mcp_client, toolsets="all") as c:
        await c.call_tool("jira_search_time_in_status", {"jql": "assignee = me"})
    params = jira.requests[0].url.params
    assert params["customjql"] == "(project = SOS) AND (assignee = me)"
    assert params["filterType"] == "customjql"


@pytest.mark.parametrize(
    "jql", ["project = SOS) OR (project = ABC", "x = 1 ORDER BY key OR project = ABC"]
)
async def test_jql_breakout_is_denied(jira, mcp_client, jql):
    async with guarded(mcp_client, toolsets="all") as c:
        await denied(c, "jira_search_sla_status", {"jql": jql})
    assert jira.requests == []


# ---------------------------------------------------------------- attachments


def _issue_with_attachment(jira, att_id="5", content=f"{BASE}/secure/attachment/5/a.txt"):
    jira.add(
        "/rest/api/2/issue/SOS-1",
        {"id": "100", "key": "SOS-1", "fields": {"attachment": [{"id": att_id}]}},
    )
    jira.add(
        f"/rest/api/2/attachment/{att_id}",
        {"filename": "a.txt", "mimeType": "text/plain", "size": 2, "content": content},
    )


async def test_attachment_requires_issue_key(jira, mcp_client):
    install_search(jira)
    _issue_with_attachment(jira)
    async with guarded(mcp_client) as c:
        body = await denied(c, "jira_get_attachment_content", {"attachment_id": "5"})
    assert "issue_key" in body["error"]
    assert jira.requests == []


async def test_attachment_of_checked_issue_is_served(jira, mcp_client):
    install_search(jira)
    _issue_with_attachment(jira)
    jira.add("/secure/attachment/5/a.txt", content=b"hi")
    async with guarded(mcp_client) as c:
        result = await c.call_tool(
            "jira_get_attachment_content", {"attachment_id": "5", "issue_key": "SOS-1"}
        )
    assert payload(result)["content"] == "hi"


async def test_attachment_of_other_issue_is_refused(jira, mcp_client):
    install_search(jira)
    _issue_with_attachment(jira)
    jira.add("/rest/api/2/attachment/9", {"content": f"{BASE}/secure/attachment/9/x"})
    async with guarded(mcp_client) as c:
        result = await c.call_tool(
            "jira_get_attachment_content",
            {"attachment_id": "9", "issue_key": "SOS-1"},
            raise_on_error=False,
        )
    assert result.is_error
    assert "/rest/api/2/attachment/9" not in [r.url.path for r in jira.requests]


async def test_attachment_link_to_another_file_or_host_is_refused(jira, mcp_client):
    """Audit finding (high): attachment URLs pointing elsewhere skipped the check."""
    install_search(jira)
    _issue_with_attachment(jira, content="https://other-jira.example.org/secure/attachment/6/x")
    async with guarded(mcp_client) as c:
        await denied(c, "jira_get_attachment_content", {"attachment_id": "5", "issue_key": "SOS-1"})
    hosts = {r.url.host for r in jira.requests}
    assert hosts == {"jira.example.com"}
    assert not any(r.url.path.startswith("/secure/") for r in jira.requests)


async def test_attachment_release_does_not_leak_between_calls(jira, mcp_client):
    install_search(jira)
    _issue_with_attachment(jira)
    jira.add("/secure/attachment/5/a.txt", content=b"hi")
    async with guarded(mcp_client) as c:
        await c.call_tool(
            "jira_get_attachment_content", {"attachment_id": "5", "issue_key": "SOS-1"}
        )
        await denied(c, "jira_get_attachment_content", {"attachment_id": "5"})


# ---------------------------------------------------------------- headers & config


class _Req:
    def __init__(self, headers: list[tuple[str, str]]):
        from starlette.datastructures import Headers

        self.headers = Headers(raw=[(k.encode(), v.encode()) for k, v in headers])


@pytest.mark.parametrize(
    "headers, message",
    [
        ([], "missing"),
        ([("x-jira-guard-jql", "  ")], "empty"),
        (
            [("x-jira-guard-jql", "project = SOS"), ("x-jira-guard-jql", "project = ABC")],
            "more than once",
        ),
        (
            [("x-jira-guard-jql", "project = SOS"), ("X-Atlassian-Jira-Url", "http://evil")],
            "not allowed",
        ),
        (
            [("x-jira-guard-jql", "project = SOS"), ("x-atlassian-confluence-url", "x")],
            "not allowed",
        ),
        ([("x-jira-guard-jql", "project = SOS) OR (1 = 1")], "unbalanced"),
    ],
)
def test_guard_header_validation(monkeypatch, headers, message):
    from atlassian_admin_mcp import guard
    from atlassian_admin_mcp.config import Settings

    monkeypatch.setattr("fastmcp.server.dependencies.get_http_request", lambda: _Req(headers))
    settings = Settings(url=BASE, personal_token="t", guard_header="x-jira-guard-jql")
    with pytest.raises(GuardDenied, match=message):
        guard.resolve_call_guard(settings)


def test_env_and_header_guards_are_combined(monkeypatch):
    from atlassian_admin_mcp import guard
    from atlassian_admin_mcp.config import Settings

    monkeypatch.setattr(
        "fastmcp.server.dependencies.get_http_request",
        lambda: _Req([("x-jira-guard-jql", "assignee = bob")]),
    )
    settings = Settings(
        url=BASE, personal_token="t", guard_jql="project = SOS", guard_header="x-jira-guard-jql"
    )
    assert guard.resolve_call_guard(settings).jql == "(project = SOS) AND (assignee = bob)"


async def test_header_mode_refuses_non_http_calls(jira, mcp_client):
    async with mcp_client(guard_header="x-jira-guard-jql") as c:
        body = await denied(c, "jira_get_issue_votes", {"issue_key": "SOS-1"})
    assert "not over HTTP" in body["error"]
    assert jira.requests == []


def test_invalid_static_guard_fails_at_startup():
    from atlassian_admin_mcp.config import ConfigError, Settings

    with pytest.raises(ConfigError, match="JIRA_GUARD_JQL"):
        Settings.from_env(
            {"JIRA_URL": BASE, "JIRA_PERSONAL_TOKEN": "t", "JIRA_GUARD_JQL": "a = 1)"}
        )


async def test_status_tool_under_guard(jira, mcp_client):
    jira.add("/rest/api/2/serverInfo", {"version": "10.3"})
    jira.add("/rest/api/2/myself", {"name": "svc"})
    async with guarded(mcp_client) as c:
        body = payload(await c.call_tool("jira_admin_status", {}))
    assert body["guard"] == {"active": True, "sources": ["JIRA_GUARD_JQL"]}
    assert "skipped" in body["groovyEndpoint"]
    assert all("atlassianAdmin" not in r.url.path for r in jira.requests)


# ---------------------------------------------------------------- secrets in logs


async def test_tokens_never_reach_logs(jira, mcp_client, caplog):
    """Audit finding (high): DEBUG logs contained Authorization headers."""
    install_search(jira)
    jira.add("/rest/api/2/issue/SOS-1/votes", {"votes": 1})
    caplog.set_level(logging.DEBUG)
    for name in ("httpx", "httpcore", "atlassian_admin_mcp", "fastmcp", "mcp"):
        logging.getLogger(name).setLevel(logging.DEBUG)
    async with guarded(mcp_client) as c:
        await c.call_tool("jira_get_issue_votes", {"issue_key": "SOS-1"})
        await c.call_tool("jira_get_issue_votes", {"issue_key": "ABC-2"}, raise_on_error=False)
    assert caplog.records, "expected debug logging to be captured"
    assert "test-token" not in caplog.text
    assert "Bearer" not in caplog.text
