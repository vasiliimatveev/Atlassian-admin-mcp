"""Behaviour of tools with non-trivial logic: fallbacks, filters, attachments."""

import base64
import json

import httpx

from .conftest import BASE, payload
from .test_tools_smoke import PNG

# ---------------------------------------------------------------- path safety


async def test_path_arguments_cannot_escape_their_endpoint(jira, mcp_client):
    async with mcp_client() as c:
        for key in ("../../plugins/1.0/", "HR-1;x", "7/../../api/2/search", "HR-1\\x"):
            result = await c.call_tool(
                "jira_get_issue_votes", {"issue_key": key}, raise_on_error=False
            )
            assert result.is_error
            assert json.loads(result.content[0].text)["kind"] == "invalid_argument"
    assert jira.requests == []


async def test_upm_plugin_key_is_encoded_and_uses_vendor_media_type(jira, mcp_client):
    jira.add("/rest/plugins/1.0/com.acme.x-key", {"key": "com.acme.x"})
    async with mcp_client() as c:
        result = await c.call_tool("jira_get_plugin", {"plugin_key": "com.acme.x"})
    assert payload(result) == {"key": "com.acme.x"}
    assert jira.requests[0].headers["Accept"] == "application/vnd.atl.plugins.plugin+json"


# ---------------------------------------------------------------- caching


async def test_repeated_config_reads_hit_jira_once(jira, mcp_client):
    jira.sr("get_workflow", {"name": "WF"})
    async with mcp_client() as c:
        for _ in range(3):
            await c.call_tool("jira_get_workflow", {"workflow_name": "WF"})
    assert len(jira.requests) == 1


async def test_volatile_reads_are_never_cached(jira, mcp_client):
    jira.add("/rest/auditing/1.0/events", {"records": []})
    jira.sr("get_system_log", {"lines": []})
    jira.sr("get_cluster_info", {"nodes": []})
    async with mcp_client() as c:
        for _ in range(2):
            await c.call_tool("jira_get_audit_log", {})
            await c.call_tool("jira_get_system_log", {})
            await c.call_tool("jira_get_cluster_info", {})
    assert len(jira.requests) == 6


# ---------------------------------------------------------------- fallbacks


async def test_sr_listeners_fall_back_to_groovy_when_rest_missing(jira, mcp_client):
    jira.sr("list_sr_listeners", [{"id": "g1"}])
    async with mcp_client() as c:
        result = await c.call_tool("jira_list_sr_listeners", {"project": "HR"})
    assert payload(result) == [{"id": "g1"}]
    sr_call = jira.requests[-1]
    assert sr_call.url.params["action"] == "list_sr_listeners"
    assert sr_call.url.params["project"] == "HR"


async def test_sr_listeners_project_filter(jira, mcp_client):
    jira.add(
        "/rest/scriptrunner-jira/latest/listeners",
        [
            {"id": "a", "projects": ["HR"]},
            {"id": "b", "projects": ["OPS"]},
            {"id": "c", "projects": []},  # global listener applies everywhere
        ],
    )
    async with mcp_client() as c:
        result = await c.call_tool("jira_list_sr_listeners", {"project": "hr"})
    assert [x["id"] for x in payload(result)] == ["a", "c"]


async def test_get_sr_listener_found_and_missing(jira, mcp_client):
    jira.add("/rest/scriptrunner-jira/latest/listeners", [{"id": "a", "script": "log.warn 1"}])
    async with mcp_client() as c:
        found = await c.call_tool("jira_get_sr_listener", {"listener_id": "a"})
        missing = await c.call_tool(
            "jira_get_sr_listener", {"listener_id": "zz"}, raise_on_error=False
        )
    assert payload(found)["script"] == "log.warn 1"
    assert missing.is_error
    assert "zz" in json.loads(missing.content[0].text)["error"]


async def test_scripted_fields_are_enriched_from_sr_rest(jira, mcp_client):
    jira.sr("list_sr_script_fields", [{"id": "customfield_1", "name": "Score"}])
    jira.add(
        "/rest/scriptrunner-jira/latest/scriptfields",
        [
            {
                "customFieldId": "customfield_1",
                "template": "float",
                "scriptFileOrScript": {"script": "1+1"},
            }
        ],
    )
    async with mcp_client() as c:
        result = await c.call_tool("jira_list_sr_script_fields", {})
    assert payload(result) == [
        {
            "id": "customfield_1",
            "name": "Score",
            "hasInlineScript": True,
            "template": "float",
            "cacheable": "",
        }
    ]


async def test_webhooks_fall_back_to_legacy_endpoint(jira, mcp_client):
    jira.add("/rest/webhooks/1.0/webhook", [{"name": "ci"}])
    async with mcp_client() as c:
        result = await c.call_tool("jira_list_webhooks", {})
    assert payload(result) == [{"name": "ci"}]
    assert jira.paths() == ["/rest/jira-webhook/1.0/webhooks", "/rest/webhooks/1.0/webhook"]


async def test_sla_definitions_fall_back_on_404(jira, mcp_client):
    jira.add("/rest/sla/1.0/definitions", [{"id": 1}])
    async with mcp_client() as c:
        result = await c.call_tool("jira_list_sla_definitions", {})
    assert payload(result) == [{"id": 1}]


async def test_sla_both_paths_missing_is_error(jira, mcp_client):
    async with mcp_client() as c:
        result = await c.call_tool("jira_list_sla_definitions", {}, raise_on_error=False)
    assert result.is_error
    assert json.loads(result.content[0].text)["kind"] == "not_found"


# ---------------------------------------------------------------- argument handling


async def test_dev_summary_resolves_issue_key(jira, mcp_client):
    jira.add("/rest/api/2/issue/HR-7", {"id": "10077"})
    jira.add("/rest/dev-status/1.0/issue/summary", {"summary": {}})
    async with mcp_client() as c:
        await c.call_tool("jira_get_issue_dev_summary", {"issue_id": "HR-7"})
    assert jira.requests[0].url.params["fields"] == "id"
    assert jira.requests[1].url.params["issueId"] == "10077"


async def test_dev_detail_validates_data_type(jira, mcp_client):
    async with mcp_client() as c:
        result = await c.call_tool(
            "jira_get_issue_dev_detail",
            {"issue_id": "1", "application_type": "stash", "data_type": "pullrequests"},
            raise_on_error=False,
        )
    assert result.is_error
    assert jira.requests == []


async def test_aql_length_and_page_size_limits(jira, mcp_client):
    jira.sr("aql_search", {"objects": []})
    jira.add("/rest/bitbucket/1.0/organization/page", {"values": []})
    async with mcp_client() as c:
        too_long = await c.call_tool("jira_aql_search", {"aql": "x" * 2001}, raise_on_error=False)
        await c.call_tool("jira_list_dvcs_organizations", {"page": 0, "page_size": 999})
    assert too_long.is_error
    params = jira.requests[-1].url.params
    assert (params["pagenum"], params["pagesize"]) == ("1", "100")


async def test_system_log_clamps_lines(jira, mcp_client):
    jira.sr("get_system_log", {"lines": []})
    async with mcp_client() as c:
        await c.call_tool("jira_get_system_log", {"lines": 10_000, "search": "ERROR"})
    params = jira.requests[0].url.params
    assert (params["lines"], params["search"]) == ("500", "ERROR")


# ---------------------------------------------------------------- attachments


def _meta(jira, name, mime, size, content_url=f"{BASE}/secure/attachment/5/f"):
    jira.add(
        "/rest/api/2/attachment/5",
        {"filename": name, "mimeType": mime, "size": size, "content": content_url},
    )


async def test_image_attachment_is_returned_as_image(jira, mcp_client):
    _meta(jira, "shot.png", "image/png", len(PNG))
    jira.add("/secure/attachment/5/f", content=PNG)
    async with mcp_client() as c:
        result = await c.call_tool("jira_get_attachment_content", {"attachment_id": "5"})
    meta, image = result.content
    assert json.loads(meta.text)["mimeType"] == "image/png"
    assert image.type == "image"
    assert base64.b64decode(image.data) == PNG


async def test_text_attachment_is_inlined_and_truncated(jira, mcp_client):
    text = "line\n" * 20_000  # 100 000 chars > 50 000 limit
    _meta(jira, "app.log", "text/plain", len(text))
    jira.add("/secure/attachment/5/f", content=text.encode())
    async with mcp_client() as c:
        result = await c.call_tool("jira_get_attachment_content", {"attachment_id": "5"})
    body = payload(result)
    assert body["truncated"] is True
    assert body["originalLength"] == 100_000
    assert len(body["content"]) == 50_000


async def test_oversized_attachment_is_not_downloaded(jira, mcp_client):
    _meta(jira, "dump.bin", "application/octet-stream", 50_000_000)
    async with mcp_client() as c:
        result = await c.call_tool("jira_get_attachment_content", {"attachment_id": "5"})
    assert "too large" in payload(result)["warning"]
    assert jira.paths() == ["/rest/api/2/attachment/5"]


async def test_attachment_url_on_foreign_host_is_rerooted(jira, mcp_client):
    _meta(
        jira, "a.txt", "text/plain", 2, content_url="https://evil.example.net/secure/attachment/5/f"
    )
    jira.add("/secure/attachment/5/f", content=b"hi")
    async with mcp_client() as c:
        result = await c.call_tool("jira_get_attachment_content", {"attachment_id": "5"})
    assert payload(result)["content"] == "hi"
    assert {r.url.host for r in jira.requests} == {"jira.example.com"}


async def test_thumbnail_missing_is_error(jira, mcp_client):
    jira.add("/rest/api/2/attachment/5", {"filename": "a.pdf", "mimeType": "application/pdf"})
    async with mcp_client() as c:
        result = await c.call_tool(
            "jira_get_attachment_thumbnail", {"attachment_id": "5"}, raise_on_error=False
        )
    assert result.is_error


async def test_download_size_lie_is_caught_while_streaming(jira, mcp_client):
    _meta(jira, "a.txt", "text/plain", 10)  # metadata claims 10 bytes

    async def big():
        for _ in range(200):
            yield b"x" * 10_000

    jira.add_handler("/secure/attachment/5/f", lambda req: httpx.Response(200, content=big()))
    async with mcp_client() as c:
        result = await c.call_tool(
            "jira_get_attachment_content", {"attachment_id": "5"}, raise_on_error=False
        )
    assert result.is_error
    assert json.loads(result.content[0].text)["kind"] == "too_large"
