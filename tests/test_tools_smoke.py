"""Call every registered tool once against a permissive fake Jira.

Catches broken ports (missing ``await``, wrong helper names, bad signatures)
and checks that each tool only talks to Jira through safe, encoded paths.
"""

import asyncio
import base64

import httpx
import pytest

from atlassian_admin_mcp.config import DEFAULT_SR_PATH
from atlassian_admin_mcp.server import create_server

from .conftest import BASE, FakeJira, make_settings

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)

# Values for required arguments, chosen to pass each tool's own validation.
SAMPLE_ARGS = {
    "issue_id": "10001",
    "issue_key": "HR-1",
    "data_type": "repository",
    "application_type": "stash",
    "aql": 'objectType = "Server"',
    "jql": "project = HR",
    "output_type": "list",
    "rule_id": "7",
    "attachment_id": "100",
}


def permissive(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.startswith("/rest/api/2/attachment/"):
        return httpx.Response(
            200,
            json={
                "filename": "shot.png",
                "size": len(PNG),
                "mimeType": "image/png",
                "content": f"{BASE}/secure/attachment/100/shot.png",
                "thumbnail": f"{BASE}/secure/thumbnail/100/shot.png",
            },
        )
    if path.startswith("/secure/"):
        return httpx.Response(200, content=PNG, headers={"Content-Type": "image/png"})
    if path.startswith("/rest/api/2/issue/") and request.url.params.get("fields") == "id":
        return httpx.Response(200, json={"id": "10001"})
    if path == DEFAULT_SR_PATH:
        return httpx.Response(200, json=[{"id": "1", "name": "x"}])
    return httpx.Response(200, json={"items": []})


def _args_for(tool) -> dict:
    schema = tool.parameters
    args = {}
    for name in schema.get("required", []):
        prop = schema["properties"][name]
        if name in SAMPLE_ARGS:
            args[name] = SAMPLE_ARGS[name]
        elif prop.get("type") == "integer":
            args[name] = 1
        elif prop.get("type") == "boolean":
            args[name] = False
        else:
            args[name] = "1"
    return args


def _all_tools():
    server = create_server(make_settings(toolsets="all"))
    return asyncio.run(server.list_tools())


ALL_TOOLS = _all_tools()


@pytest.mark.parametrize("tool", ALL_TOOLS, ids=[t.name for t in ALL_TOOLS])
async def test_every_tool_runs(tool):
    from fastmcp import Client

    jira = FakeJira()
    jira.fallback = permissive
    server = create_server(make_settings(toolsets="all"), transport=httpx.MockTransport(jira))
    async with Client(server) as c:
        result = await c.call_tool(tool.name, _args_for(tool), raise_on_error=False)

    assert not result.is_error, result.content[0].text
    assert result.content, "empty result"
    assert jira.requests, "tool made no HTTP request"
    for req in jira.requests:
        assert req.url.host == "jira.example.com"
        assert req.headers["Authorization"] == "Bearer test-token"
        assert "/../" not in req.url.raw_path.decode()
