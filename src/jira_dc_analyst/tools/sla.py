"""Toolset ``sla`` — Time to SLA (Appfire/SaaSJet)."""

import logging
from collections.abc import Callable
from typing import Annotated, Any

from fastmcp import Context
from pydantic import Field

from ..client import AnalystError
from ..util import error_json, get_client, to_json

logger = logging.getLogger(__name__)


def register(tool: Callable[..., Any]) -> None:  # noqa: C901 — flat list of thin wrappers
    # =====================================================================
    # Appfire / SaaSJet "Time to SLA" (Marketplace 1211843) — /rest/sla/1.0/
    #
    # The plugin's namespace is confirmed by Appfire's public DC docs
    # (appfire.atlassian.net/wiki/spaces/TTS/). Exact leaf paths were not
    # available in machine-readable form at the time of porting; the paths
    # below follow the most widely-cited patterns from Appfire/SaaSJet
    # blog posts and support articles. If a call returns 404, fall back
    # to the Postman collection linked from the Appfire docs.
    # =====================================================================

    @tool(
        tags={"read", "toolset:sla"},
        annotations={"title": "List SLA Definitions", "readOnlyHint": True},
    )
    async def list_sla_definitions(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """List all SLA definitions configured by the Time to SLA plugin.

        Each definition: id, name, JQL scope, goals, calendar id. Admin-only
        in most configurations. Backed by ``GET /rest/sla/1.0/slas`` with
        automatic fallback to the older ``/rest/sla/1.0/definitions`` path
        on 404.
        """
        client = get_client(ctx)
        try:
            return to_json(await client.rest_get("/rest/sla/1.0/slas"))
        except AnalystError as exc:
            if exc.status == 404:
                try:
                    return to_json(await client.rest_get("/rest/sla/1.0/definitions"))
                except AnalystError as exc2:
                    return error_json(
                        "list_sla_definitions failed on both known leaf "
                        "paths (/slas and /definitions)",
                        status=exc2.status,
                        detail=str(exc2),
                    )
            return error_json(f"list_sla_definitions failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:sla"},
        annotations={"title": "List SLA Calendars", "readOnlyHint": True},
    )
    async def list_sla_calendars(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """List work calendars used for SLA calculations — working days, hours, holidays.

        Backed by ``GET /rest/sla/1.0/calendars`` with automatic fallback
        to ``/rest/sla/1.0/slas/calendars`` on 404 (older plugin layout).
        """
        client = get_client(ctx)
        try:
            return to_json(await client.rest_get("/rest/sla/1.0/calendars"))
        except AnalystError as exc:
            if exc.status == 404:
                try:
                    return to_json(await client.rest_get("/rest/sla/1.0/slas/calendars"))
                except AnalystError as exc2:
                    return error_json(
                        "list_sla_calendars failed on both known leaf paths",
                        status=exc2.status,
                        detail=str(exc2),
                    )
            return error_json(f"list_sla_calendars failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:sla"},
        annotations={"title": "Search SLA Status by JQL", "readOnlyHint": True},
    )
    async def search_sla_status(
        ctx: Context,
        jql: Annotated[
            str,
            Field(description="JQL selecting issues whose SLA status you want."),
        ],
        start_at: Annotated[int, Field(description="Pagination start (0-based).")] = 0,
        max_results: Annotated[int, Field(description="Page size (1..100 per plugin docs).")] = 50,
    ) -> str:
        """Per-issue SLA status across a JQL result set.

        Returns each issue with its SLAs (elapsed / remaining / paused /
        breached / startDate / targetDate / stopDate / calendarId). The
        most valuable analyst endpoint of this plugin — answers "which
        tickets are breached" and "which SLAs are close to breach" in a
        single call.

        If this 404s, the instance may expose the endpoint as
        ``/rest/sla/1.0/slaSearch``. Try that manually.
        """
        if not jql.strip():
            return error_json("jql is required")
        params = {
            "jql": jql,
            "startAt": max(0, int(start_at)),
            "maxResults": max(1, min(int(max_results), 100)),
        }
        client = get_client(ctx)
        try:
            return to_json(await client.rest_get("/rest/sla/1.0/search", **params))
        except AnalystError as exc:
            if exc.status == 404:
                try:
                    return to_json(await client.rest_get("/rest/sla/1.0/slaSearch", **params))
                except AnalystError as exc2:
                    return error_json(
                        "search_sla_status failed on both known leaf paths",
                        status=exc2.status,
                        detail=str(exc2),
                    )
            return error_json(f"search_sla_status failed: {exc}", status=exc.status)
