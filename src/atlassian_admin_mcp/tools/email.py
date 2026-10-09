"""Toolset ``email`` — Email This Issue (JETI) audit log and mail queues."""

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
    # MetaInf "Email This Issue" (JETI, Marketplace 4977) — /rest/jeti/1.0/
    #
    # Vendor docs: https://docs.meta-inf.hu/email-this-issue/
    # Public REST only covers the audit log and queue metrics; template /
    # notification-rule / handler CRUD is exposed via OSGi API only and
    # would require ScriptRunner. For audit needs ("why did this issue
    # get an email", "is the queue backing up") the REST surface is enough.
    # =====================================================================

    @tool(
        tags={"read", "toolset:email"},
        annotations={"title": "Search JETI Email Audit", "readOnlyHint": True},
    )
    async def search_jeti_audit_log(
        ctx: Context,
        issue_key: Annotated[
            str,
            Field(description="Filter by Jira issue key (e.g. 'HR-123')."),
        ] = "",
        recipient: Annotated[
            str,
            Field(description="Filter by recipient email address or username."),
        ] = "",
        template: Annotated[str, Field(description="Filter by email-template name or id.")] = "",
        from_date: Annotated[
            str,
            Field(description="ISO date ('2026-03-01') — audit records from this date."),
        ] = "",
        to_date: Annotated[
            str, Field(description="ISO date — audit records up to this date.")
        ] = "",
        limit: Annotated[int, Field(description="Max records to return (1..1000).")] = 100,
    ) -> str:
        """Find who received what email for a Jira issue and when.

        Audit log of emails sent by the Email This Issue (JETI) plugin.
        Filters: issue key, recipient, template, date range, limit. Results
        are filtered by the plugin to what the caller has permission to see
        (issue browse at minimum). Backed by
        ``GET /rest/jeti/1.0/email/query``.
        """
        params: dict[str, Any] = {"limit": max(1, min(int(limit), 1000))}
        if issue_key:
            params["issueKey"] = issue_key
        if recipient:
            params["recipient"] = recipient
        if template:
            params["template"] = template
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        client = get_client(ctx)
        try:
            return to_json(await client.rest_get("/rest/jeti/1.0/email/query", **params))
        except JiraError as exc:
            return error_json(f"search_jeti_audit_log failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:email"},
        annotations={"title": "JETI Audit Count", "readOnlyHint": True},
    )
    async def get_jeti_audit_count(
        ctx: Context,
        issue_key: Annotated[str, Field(description="Optional issue key.")] = "",
        recipient: Annotated[str, Field(description="Optional recipient.")] = "",
        template: Annotated[str, Field(description="Optional template.")] = "",
        from_date: Annotated[str, Field(description="ISO date.")] = "",
        to_date: Annotated[str, Field(description="ISO date.")] = "",
    ) -> str:
        """Count JETI audit-log entries matching a filter — cheap sanity check.

        Run this before a heavy ``search_jeti_audit_log`` if you only need
        "how many emails went out". Backed by ``GET /rest/jeti/1.0/email/stat``.
        """
        params: dict[str, Any] = {}
        if issue_key:
            params["issueKey"] = issue_key
        if recipient:
            params["recipient"] = recipient
        if template:
            params["template"] = template
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        client = get_client(ctx)
        try:
            return to_json(await client.rest_get("/rest/jeti/1.0/email/stat", **params))
        except JiraError as exc:
            return error_json(f"get_jeti_audit_count failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:email"},
        annotations={"title": "JETI Outgoing Mail Queue", "readOnlyHint": True},
    )
    async def get_jeti_outgoing_queue_stats(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """Diagnose "JETI emails aren't arriving" — outbound mail queue stats.

        Shows queue depth and processing lag. JETI v9.0.0+ only. Backed by
        ``GET /rest/jeti/1.0/outgoingMailQueue/statistic``.
        """
        client = get_client(ctx)
        try:
            return to_json(
                await client.rest_get("/rest/jeti/1.0/outgoingMailQueue/statistic", cache=False)
            )
        except JiraError as exc:
            return error_json(
                f"get_jeti_outgoing_queue_stats failed: {exc}",
                status=exc.status,
                hint=("Requires JETI v9.0.0+. Older versions return 404 on queue endpoints."),
            )

    @tool(
        tags={"read", "toolset:email"},
        annotations={"title": "JETI Incoming Mail Queue", "readOnlyHint": True},
    )
    async def get_jeti_incoming_queue_stats(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """Diagnose inbound JETI mail handlers — are they processing or stuck.

        Queue depth and lag for incoming mail. JETI v9.0.0+ only. Backed by
        ``GET /rest/jeti/1.0/incomingMailQueue/statistic``.
        """
        client = get_client(ctx)
        try:
            return to_json(
                await client.rest_get("/rest/jeti/1.0/incomingMailQueue/statistic", cache=False)
            )
        except JiraError as exc:
            return error_json(
                f"get_jeti_incoming_queue_stats failed: {exc}",
                status=exc.status,
                hint="Requires JETI v9.0.0+.",
            )

    @tool(
        tags={"read", "toolset:email"},
        annotations={"title": "JETI Mail Generation Queue", "readOnlyHint": True},
    )
    async def get_jeti_generation_queue_stats(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """Spot bottlenecks between JETI event firing and email send — template-rendering queue.

        Diagnostic for "event fired but no email yet". JETI v9.0.0+ only.
        Backed by ``GET /rest/jeti/1.0/mailGenerationQueue/statistic``.
        """
        client = get_client(ctx)
        try:
            return to_json(
                await client.rest_get("/rest/jeti/1.0/mailGenerationQueue/statistic", cache=False)
            )
        except JiraError as exc:
            return error_json(
                f"get_jeti_generation_queue_stats failed: {exc}",
                status=exc.status,
                hint="Requires JETI v9.0.0+.",
            )
