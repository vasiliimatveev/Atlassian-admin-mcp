"""Toolset ``time_in_status`` — Timepiece — Time in Status (OBSS)."""

import logging
from collections.abc import Callable
from typing import Annotated, Any

from fastmcp import Context
from pydantic import Field

from ..client import JiraError
from ..util import error_json, get_client, to_json

logger = logging.getLogger(__name__)


def register(tool: Callable[..., Any]) -> None:
    # =====================================================================
    # OBSS "Timepiece — Time in Status for Jira" (Marketplace 1211756)
    # Public REST at /rest/tis/report/1.0/ — well-documented:
    # https://documentation.obss.tech/timepiece-time-in-status-for-jira-data-center/
    #
    # The plugin's legacy /api/list was deprecated after August 2025 when
    # Atlassian's JQL search API changed; we target the modern /api/list2
    # only, which uses cursor-paging and supports up to 1000 issues/page.
    # =====================================================================

    @tool(
        tags={"read", "toolset:time_in_status"},
        annotations={"title": "Get Time-in-Status for Issue", "readOnlyHint": True},
    )
    async def get_issue_time_in_status(
        ctx: Context,
        issue_key: Annotated[str, Field(description="Issue key, e.g. 'HR-123'.")],
        columns_by: Annotated[
            str,
            Field(
                description=(
                    "Breakdown axis: 'statuses' (default), 'assignees', "
                    "'groups', or a custom-field id for custom-breakdowns."
                )
            ),
        ] = "statuses",
        calendar: Annotated[
            str,
            Field(
                description=(
                    "Optional work-calendar id (from ``list_tis_calendars``). Omit for 24×7."
                )
            ),
        ] = "",
        view_format: Annotated[
            str,
            Field(
                description=(
                    "'duration' (e.g. '2d 3h'), 'decimal' (hours), or "
                    "'raw-seconds'. Default 'raw-seconds' — easier to "
                    "post-process programmatically."
                )
            ),
        ] = "raw-seconds",
    ) -> str:
        """Get time-in-status breakdown for one issue — how long it sat in each status.

        Returns seconds per status (or per assignee / group / custom-field
        bucket depending on ``columns_by``). Any authenticated user with
        Browse permission can call. Backed by
        ``GET /rest/tis/report/1.0/api/issue``.
        """
        params: dict[str, Any] = {
            "issueKey": issue_key,
            "columnsBy": columns_by,
            "viewFormat": view_format,
        }
        if calendar:
            params["calendar"] = calendar
        client = get_client(ctx)
        try:
            return to_json(await client.rest_get("/rest/tis/report/1.0/api/issue", **params))
        except JiraError as exc:
            return error_json(f"get_issue_time_in_status failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:time_in_status"},
        annotations={"title": "Search Time-in-Status by JQL", "readOnlyHint": True},
    )
    async def search_time_in_status(
        ctx: Context,
        jql: Annotated[
            str,
            Field(description="JQL selecting target issues (custom JQL filter mode)."),
        ],
        output_type: Annotated[
            str,
            Field(
                description=(
                    "'list' = per-issue breakdown, 'average' = average per "
                    "status across the set, 'sum' = totals across the set."
                )
            ),
        ] = "list",
        columns_by: Annotated[
            str,
            Field(description="'statuses', 'assignees', 'groups', or custom-field id."),
        ] = "statuses",
        page_size: Annotated[
            int,
            Field(description="Cursor page size (1..1000). Default 200."),
        ] = 200,
        next_page_token: Annotated[
            str,
            Field(
                description=(
                    "Cursor from a previous call's ``nextPageToken``. Leave "
                    "empty for the first page."
                )
            ),
        ] = "",
        view_format: Annotated[
            str, Field(description="'duration', 'decimal', or 'raw-seconds'.")
        ] = "raw-seconds",
        calendar: Annotated[str, Field(description="Optional work-calendar id.")] = "",
    ) -> str:
        """Run a bulk time-in-status report across a JQL — per-issue, average, or sum.

        Answers "how long do tickets sit in Code Review on average" or
        "team throughput by status this quarter". Three output modes:

        * ``list`` — per-issue seconds-in-each-status table
        * ``average`` — average per status across the JQL set
        * ``sum`` — total across the set

        Backed by ``GET /rest/tis/report/1.0/api/list2`` (cursor-paginated,
        ~20× faster than the deprecated ``/api/list`` which stopped working
        after Atlassian's Aug 2025 JQL search API change).
        """
        if not jql.strip():
            return error_json("jql is required")
        if output_type not in ("list", "average", "sum"):
            return error_json("output_type must be 'list', 'average', or 'sum'")
        params: dict[str, Any] = {
            "filterType": "customjql",
            "customjql": jql,
            "outputType": output_type,
            "columnsBy": columns_by,
            "pageSize": max(1, min(int(page_size), 1000)),
            "viewFormat": view_format,
        }
        if next_page_token:
            params["nextPageToken"] = next_page_token
        if calendar:
            params["calendar"] = calendar
        client = get_client(ctx)
        try:
            return to_json(await client.rest_get("/rest/tis/report/1.0/api/list2", **params))
        except JiraError as exc:
            return error_json(f"search_time_in_status failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:time_in_status"},
        annotations={"title": "List TIS Calendars", "readOnlyHint": True},
    )
    async def list_tis_calendars(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """List work calendars configured for Time-in-Status reports.

        Returns calendar ids + working days/hours/holidays. Accepted by
        ``get_issue_time_in_status`` / ``search_time_in_status`` as the
        ``calendar`` param. Backed by ``GET /rest/tis/report/1.0/data/calendars``.
        """
        client = get_client(ctx)
        try:
            return to_json(await client.rest_get("/rest/tis/report/1.0/data/calendars"))
        except JiraError as exc:
            return error_json(f"list_tis_calendars failed: {exc}", status=exc.status)
