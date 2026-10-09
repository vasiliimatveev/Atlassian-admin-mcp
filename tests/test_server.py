import json
import re

import pytest

from atlassian_admin_mcp.toolsets import TOOLSETS

from .conftest import payload

EXPECTED_COUNTS = {
    "admin": 45,
    "scriptrunner": 11,
    "jmwe": 4,
    "structure": 7,
    "assets": 10,
    "automation": 2,
    "logs": 2,
    "integrations": 6,
    "issue_inspect": 4,
    "dvcs": 10,
    "properties": 6,
    "sla": 3,
    "time_in_status": 3,
    "email": 5,
}


def _toolset(tool) -> str:
    tags = tool.meta["fastmcp"]["tags"]
    return next(t.removeprefix("toolset:") for t in tags if t.startswith("toolset:"))


async def test_all_toolsets_register_expected_tools(mcp_client):
    async with mcp_client(toolsets="all") as c:
        tools = await c.list_tools()
    counts: dict[str, int] = {}
    for t in tools:
        counts[_toolset(t)] = counts.get(_toolset(t), 0) + 1
    assert counts.pop("core") == 1
    assert counts == EXPECTED_COUNTS
    assert set(EXPECTED_COUNTS) == set(TOOLSETS)


async def test_only_enabled_toolsets_are_exposed(mcp_client):
    async with mcp_client(toolsets="jmwe,logs") as c:
        names = {t.name for t in await c.list_tools()}
    assert names == {
        "jira_admin_status",
        "jira_list_jmwe_event_actions",
        "jira_get_jmwe_event_action",
        "jira_list_jmwe_shared_actions",
        "jira_get_jmwe_shared_action",
        "jira_get_audit_log",
        "jira_get_system_log",
    }


async def test_unknown_toolsets_leave_only_status_tool(mcp_client):
    async with mcp_client(toolsets="nope") as c:
        assert [t.name for t in await c.list_tools()] == ["jira_admin_status"]


async def test_tool_metadata_is_agent_friendly(mcp_client):
    async with mcp_client(toolsets="all") as c:
        tools = await c.list_tools()
    names = [t.name for t in tools]
    assert len(names) == len(set(names))
    for t in tools:
        assert re.fullmatch(r"jira_[a-z0-9_]+", t.name), t.name
        assert len(t.name) <= 64, t.name
        assert t.description and t.description.strip(), t.name
        assert t.annotations.read_only_hint is True, t.name
        assert t.annotations.destructive_hint is False, t.name
        assert t.annotations.title, t.name
        # JSON text only — no duplicated structuredContent.
        assert t.output_schema is None, t.name
        schema = t.input_schema
        assert "ctx" not in schema.get("properties", {}), t.name
        for pname, prop in schema.get("properties", {}).items():
            assert prop.get("description"), f"{t.name}.{pname} has no description"


async def test_tools_return_compact_json_without_structured_duplicate(jira, mcp_client):
    jira.sr("list_workflows", [{"name": "Default", "steps": 3}])
    async with mcp_client() as c:
        result = await c.call_tool("jira_list_workflows", {})
    assert result.structured_content is None
    assert result.content[0].text == '[{"name":"Default","steps":3}]'


# ---------------------------------------------------------------- errors


async def _error(c, name, args):
    result = await c.call_tool(name, args, raise_on_error=False)
    assert result.is_error, result
    return json.loads(result.content[0].text)


async def test_missing_groovy_endpoint_is_explained(jira, mcp_client):
    async with mcp_client() as c:
        err = await _error(c, "jira_list_workflows", {})
    assert err["kind"] == "groovy_endpoint_missing"
    assert err["status"] == 404
    assert "atlassian_admin.groovy" in err["hint"]
    assert err["retryable"] is False


async def test_groovy_forbidden_vs_plain_forbidden(jira, mcp_client):
    jira.sr("list_workflows", {"message": "no"}, status=403)
    jira.add("/rest/auditing/1.0/events", {}, status=403)
    async with mcp_client() as c:
        assert (await _error(c, "jira_list_workflows", {}))["kind"] == "groovy_forbidden"
        assert (await _error(c, "jira_get_audit_log", {}))["kind"] == "forbidden"


@pytest.mark.parametrize(
    "status, kind, retryable",
    [(401, "auth_failed", False), (500, "jira_error", False), (503, "jira_busy", True)],
)
async def test_status_kinds(jira, mcp_client, status, kind, retryable):
    jira.add("/rest/auditing/1.0/events", {}, status=status)
    async with mcp_client() as c:
        err = await _error(c, "jira_get_audit_log", {})
    assert (err["kind"], err["retryable"]) == (kind, retryable)


async def test_returned_error_payloads_become_is_error(jira, mcp_client):
    """Tools that catch failures and return {"error": ...} still flag isError."""
    async with mcp_client() as c:
        err = await _error(c, "jira_get_issue_votes", {"issue_key": "HR-1"})
    assert err["status"] == 404
    assert err["kind"] == "not_found"


async def test_groovy_error_body_becomes_is_error(jira, mcp_client):
    jira.sr("get_system_log", {"error": "Log file not found", "path": "/x"})
    async with mcp_client() as c:
        err = await _error(c, "jira_get_system_log", {})
    assert err["error"] == "Log file not found"
    assert err["kind"] == "failed"


async def test_invalid_path_argument_is_rejected_before_any_request(jira, mcp_client):
    async with mcp_client() as c:
        err = await _error(c, "jira_get_issue_votes", {"issue_key": ".."})
    assert err["kind"] == "invalid_argument"
    assert jira.requests == []


async def test_unreachable_jira(jira, mcp_client):
    import httpx

    def down(request):
        raise httpx.ConnectError("refused", request=request)

    jira.fallback = down
    async with mcp_client() as c:
        err = await _error(c, "jira_get_audit_log", {})
    assert err["kind"] == "unreachable"
    assert err["retryable"] is True


async def test_large_responses_are_truncated_with_marker(jira, mcp_client):
    jira.sr("list_workflows", [{"name": "x" * 500}] * 10)
    async with mcp_client(max_response_chars=1000) as c:
        result = await c.call_tool("jira_list_workflows", {})
    body = payload(result)
    assert body["truncated"] is True
    assert body["returnedChars"] == 1000
    assert body["totalChars"] > 1000
    assert len(body["partial"]) == 1000


# ---------------------------------------------------------------- status tool


async def test_status_reports_everything_ok(jira, mcp_client):
    jira.add("/rest/api/2/serverInfo", {"version": "10.3.2", "deploymentType": "Server"})
    jira.add("/rest/api/2/myself", {"name": "admin", "displayName": "Admin"})
    jira.sr("ping", {"ok": True, "endpointVersion": "2.0.0"})
    async with mcp_client(toolsets="default") as c:
        body = payload(await c.call_tool("jira_admin_status", {}))
    assert body["jira"] == {
        "ok": True,
        "version": "10.3.2",
        "deploymentType": "Server",
        "baseUrl": None,
    }
    assert body["user"]["name"] == "admin"
    assert body["groovyEndpoint"]["ok"] is True
    assert body["groovyEndpoint"]["endpointVersion"] == "2.0.0"
    assert body["toolsets"]["admin"]["enabled"] is True
    assert body["toolsets"]["jmwe"]["enabled"] is False
    assert body["cache"]["enabled"] is True


async def test_status_explains_partial_failures(jira, mcp_client):
    jira.add("/rest/api/2/serverInfo", {"version": "9.12.0"})
    jira.add("/rest/api/2/myself", {}, status=401)
    async with mcp_client() as c:
        result = await c.call_tool("jira_admin_status", {})
    assert not result.is_error
    body = payload(result)
    assert body["jira"]["ok"] is True
    assert body["user"]["kind"] == "auth_failed"
    assert body["groovyEndpoint"]["kind"] == "groovy_endpoint_missing"


async def test_status_flags_outdated_groovy_endpoint(jira, mcp_client):
    jira.add("/rest/api/2/serverInfo", {})
    jira.add("/rest/api/2/myself", {})
    jira.sr("ping", {"error": "Unknown action: 'ping'"})  # pre-2.0 endpoint answers 200
    async with mcp_client() as c:
        body = payload(await c.call_tool("jira_admin_status", {}))
    assert "older atlassian_admin.groovy" in body["groovyEndpoint"]["warning"]


async def test_status_never_uses_cache(jira, mcp_client):
    jira.add("/rest/api/2/serverInfo", {})
    jira.add("/rest/api/2/myself", {})
    jira.sr("ping", {"ok": True})
    async with mcp_client() as c:
        await c.call_tool("jira_admin_status", {})
        await c.call_tool("jira_admin_status", {"clear_cache": True})
    assert len(jira.requests) == 6
