"""Toolset ``logs`` — Audit log and atlassian-jira.log tail."""

import logging
from collections.abc import Callable
from typing import Annotated, Any

from fastmcp import Context
from pydantic import Field

from ..util import get_client, to_json

logger = logging.getLogger(__name__)


def register(tool: Callable[..., Any]) -> None:
    # =====================================================================
    # Audit + System logs
    # =====================================================================

    @tool(
        tags={"read", "toolset:logs"},
        annotations={"title": "Get Audit Log", "readOnlyHint": True},
    )
    async def get_audit_log(
        ctx: Context,
        limit: Annotated[int, Field(description="Max records (1..1000).")] = 50,
        offset: Annotated[int, Field(description="Pagination offset.")] = 0,
        from_date: Annotated[str, Field(description="ISO date, e.g. '2026-03-01'.")] = "",
        to_date: Annotated[str, Field(description="ISO date.")] = "",
        search: Annotated[str, Field(description="Free-text filter.")] = "",
    ) -> str:
        """Admin audit events — permission changes, scheme edits, user management."""
        client = get_client(ctx)
        params: dict[str, Any] = {
            "limit": min(max(limit, 1), 1000),
            "offset": max(offset, 0),
        }
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if search:
            params["searchString"] = search
        return to_json(await client.rest_get("/rest/auditing/1.0/events", cache=False, **params))

    @tool(
        tags={"read", "toolset:logs"},
        annotations={"title": "Get System Log", "readOnlyHint": True},
    )
    async def get_system_log(
        ctx: Context,
        lines: Annotated[int, Field(description="How many lines to return (1..500).")] = 100,
        search: Annotated[
            str,
            Field(
                description=(
                    "Case-insensitive substring, e.g. 'ERROR', 'OutOfMemory', 'HR-'. "
                    "With a filter the endpoint scans up to the last 50 MB of the "
                    "log and returns the newest matching lines."
                )
            ),
        ] = "",
    ) -> str:
        """Tail of atlassian-jira.log for debugging plugin errors and startup issues.

        Reads the current log file backwards, so the cost does not grow with
        file size. Rotated files (``atlassian-jira.log.1`` …) are not scanned;
        ``scanLimitReached`` in the result says the filter hit the scan cap.
        """
        client = get_client(ctx)
        lines = max(1, min(int(lines), 500))
        return to_json(
            await client.sr_action("get_system_log", cache=False, lines=str(lines), search=search)
        )
