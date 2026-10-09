"""Toolset ``scriptrunner`` — Listeners, behaviours, scripted fields, fragments, jobs, REST endpoints, escalation services — with full Groovy source."""

import logging
from collections.abc import Callable
from typing import Annotated, Any

from fastmcp import Context
from pydantic import Field

from ..client import JiraError
from ..util import error_json, get_client, to_json

logger = logging.getLogger(__name__)


def register(tool: Callable[..., Any]) -> None:  # noqa: C901 — flat list of thin wrappers
    # =====================================================================
    # ScriptRunner
    # =====================================================================

    @tool(
        tags={"read", "toolset:scriptrunner"},
        annotations={"title": "List ScriptRunner Listeners", "readOnlyHint": True},
    )
    async def list_sr_listeners(
        ctx: Context,
        project: Annotated[
            str,
            Field(description="Optional project key filter (e.g. 'HR')."),
        ] = "",
    ) -> str:
        """Listeners with events, script file, enabled state, projects, inline scripts."""
        client = get_client(ctx)
        try:
            data = await client.rest_get("/rest/scriptrunner-jira/latest/listeners")
            if isinstance(data, list):
                if project:
                    p = project.upper()
                    data = [
                        listener
                        for listener in data
                        if p in [pk.upper() for pk in (listener.get("projects") or [])]
                        or p in (listener.get("FIELD_NOTES", "") or "").upper()
                        or p in (listener.get("notes", "") or "").upper()
                        or not listener.get("projects")
                    ]
                return to_json(data)
        except JiraError as exc:
            logger.info("SR REST listeners unavailable (%s); falling back to Groovy", exc)
        return to_json(await client.sr_action("list_sr_listeners", project=project))

    @tool(
        tags={"read", "toolset:scriptrunner"},
        annotations={"title": "Get ScriptRunner Listener", "readOnlyHint": True},
    )
    async def get_sr_listener(
        ctx: Context,
        listener_id: Annotated[str, Field(description="Listener id/uuid.")],
    ) -> str:
        """FULL Groovy script + event bindings for a single listener."""
        client = get_client(ctx)
        try:
            all_listeners = await client.rest_get("/rest/scriptrunner-jira/latest/listeners")
            if isinstance(all_listeners, list):
                for listener in all_listeners:
                    lid = listener.get("id") or listener.get("uuid") or ""
                    if str(lid) == listener_id:
                        return to_json(listener)
                return error_json(f"Listener {listener_id} not found", status=404)
        except JiraError as exc:
            logger.info(
                "SR REST listener fetch failed for id=%s (%s); falling back",
                listener_id,
                exc,
            )
        return to_json(await client.sr_action("get_sr_listener", id=listener_id))

    @tool(
        tags={"read", "toolset:scriptrunner"},
        annotations={"title": "List ScriptRunner Behaviours", "readOnlyHint": True},
    )
    async def list_sr_behaviours(
        ctx: Context,
        project: Annotated[str, Field(description="Optional project key filter.")] = "",
    ) -> str:
        """Form behaviours — id, name, disabled, field count (no scripts)."""
        client = get_client(ctx)
        data = await client.sr_action("list_sr_behaviours", project=project)
        if project and isinstance(data, list) and len(data) > 50:
            p = project.upper()
            data = [
                b
                for b in data
                if p in (b.get("name", "") or "").upper()
                or p in (b.get("guideWorkflow", "") or "").upper()
            ]
        return to_json(data)

    @tool(
        tags={"read", "toolset:scriptrunner"},
        annotations={"title": "Get ScriptRunner Behaviour", "readOnlyHint": True},
    )
    async def get_sr_behaviour(
        ctx: Context,
        behaviour_id: Annotated[str, Field(description="Behaviour id.")],
    ) -> str:
        """FULL Groovy per field — server-side validation, initialisers, conditions."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_sr_behaviour", id=behaviour_id))

    @tool(
        tags={"read", "toolset:scriptrunner"},
        annotations={"title": "List ScriptRunner Scripted Fields", "readOnlyHint": True},
    )
    async def list_sr_script_fields(
        ctx: Context,
        project: Annotated[str, Field(description="Optional project key filter.")] = "",
    ) -> str:
        """Scripted fields — field name, template, hasInlineScript, scriptFile path."""
        client = get_client(ctx)
        data = await client.sr_action("list_sr_script_fields", project=project)
        try:
            sr_fields = await client.rest_get("/rest/scriptrunner-jira/latest/scriptfields")
            if isinstance(sr_fields, list) and isinstance(data, list):
                sr_map: dict[str, dict[str, Any]] = {}
                for sf in sr_fields:
                    cf_id = sf.get("customFieldId") or sf.get("fieldId") or ""
                    if cf_id:
                        sr_map[str(cf_id)] = sf
                for item in data:
                    field_id = item.get("id", "")
                    sr_config = sr_map.get(field_id)
                    if sr_config:
                        sfos = (
                            sr_config.get("scriptFileOrScript")
                            or sr_config.get("FIELD_SCRIPT_FILE_OR_SCRIPT")
                            or {}
                        )
                        if isinstance(sfos, dict):
                            if sfos.get("script"):
                                item["hasInlineScript"] = True
                            if sfos.get("scriptFile"):
                                item["scriptFile"] = sfos["scriptFile"]
                        item["template"] = sr_config.get("template", "")
                        item["cacheable"] = sr_config.get("cacheable", "")
        except JiraError as exc:
            logger.info("SR scriptfields enrichment failed (%s); returning base", exc)
        return to_json(data)

    @tool(
        tags={"read", "toolset:scriptrunner"},
        annotations={"title": "Get ScriptRunner Scripted Field", "readOnlyHint": True},
    )
    async def get_sr_script_field(
        ctx: Context,
        field_id: Annotated[
            str,
            Field(
                description=("Field id — 'customfield_10123', bare numeric '10123', or field name.")
            ),
        ],
    ) -> str:
        """FULL Groovy, template type, caching config, preview issue."""
        client = get_client(ctx)
        try:
            all_fields = await client.rest_get("/rest/scriptrunner-jira/latest/scriptfields")
            if isinstance(all_fields, list):
                cf_num = field_id.replace("customfield_", "")
                for field in all_fields:
                    cf_id = str(field.get("customFieldId", ""))
                    if cf_id in (cf_num, field_id) or field.get("name") == field_id:
                        return to_json(field)
                return error_json(f"Scripted field {field_id} not found in SR config", status=404)
        except JiraError as exc:
            logger.info(
                "SR REST scriptfield fetch failed for id=%s (%s); falling back",
                field_id,
                exc,
            )
        return to_json(await client.sr_action("get_sr_script_field", id=field_id))

    @tool(
        tags={"read", "toolset:scriptrunner"},
        annotations={"title": "List ScriptRunner Fragments", "readOnlyHint": True},
    )
    async def list_sr_fragments(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """Web items, panels, sections, and show/hide conditions injected into the UI."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_sr_fragments"))

    @tool(
        tags={"read", "toolset:scriptrunner"},
        annotations={"title": "List ScriptRunner Jobs", "readOnlyHint": True},
    )
    async def list_sr_jobs(
        ctx: Context,
        project: Annotated[str, Field(description="Optional project key filter.")] = "",
    ) -> str:
        """Scheduled jobs — name, cron, last run, script file, enabled state."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_sr_jobs", project=project))

    @tool(
        tags={"read", "toolset:scriptrunner"},
        annotations={"title": "List ScriptRunner REST Endpoints", "readOnlyHint": True},
    )
    async def list_sr_endpoints(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """Custom REST endpoints found under JIRA_HOME/scripts — name, method, preview."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_sr_endpoints"))

    @tool(
        tags={"read", "toolset:scriptrunner"},
        annotations={"title": "List ScriptRunner Escalations", "readOnlyHint": True},
    )
    async def list_sr_escalation_services(
        ctx: Context,
        project: Annotated[str, Field(description="Optional project key filter.")] = "",
    ) -> str:
        """JQL-based scheduled rules that auto-transition or modify issues."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_sr_escalation_services", project=project))

    @tool(
        tags={"read", "toolset:scriptrunner"},
        annotations={"title": "Get ScriptRunner Escalation", "readOnlyHint": True},
    )
    async def get_sr_escalation_service(
        ctx: Context,
        service_id: Annotated[str, Field(description="Escalation service id.")],
    ) -> str:
        """Full JQL, cron schedule, transition/script actions, enabled state."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_sr_escalation_service", id=service_id))
