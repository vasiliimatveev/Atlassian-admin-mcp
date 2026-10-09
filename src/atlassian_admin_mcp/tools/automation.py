"""Toolset ``automation`` — Automation for Jira rules."""

import logging
from collections.abc import Callable
from typing import Annotated, Any

from fastmcp import Context
from pydantic import Field

from ..client import JiraError
from ..util import error_json, get_client, seg, to_json

logger = logging.getLogger(__name__)


def register(tool: Callable[..., Any]) -> None:
    # =====================================================================
    # Automation for Jira (A4J)
    # =====================================================================

    @tool(
        tags={"read", "toolset:automation"},
        annotations={"title": "List A4J Rules", "readOnlyHint": True},
    )
    async def list_a4j_rules(
        ctx: Context,
        project: Annotated[
            str,
            Field(description="Project key. A4J may require project scope."),
        ] = "",
    ) -> str:
        """List Automation for Jira rules — id, name, state, description."""
        client = get_client(ctx)
        if project:
            return to_json(
                await client.rest_get(f"/rest/cb-automation/latest/project/{seg(project)}/rule")
            )
        try:
            return to_json(await client.rest_get("/rest/cb-automation/latest/rule"))
        except JiraError as exc:
            logger.info("A4J global rules endpoint failed (%s)", exc)
            return error_json("project parameter required for A4J rules")

    @tool(
        tags={"read", "toolset:automation"},
        annotations={"title": "Get A4J Rule", "readOnlyHint": True},
    )
    async def get_a4j_rule(
        ctx: Context,
        rule_id: Annotated[str, Field(description="A4J rule id.")],
        project: Annotated[str, Field(description="Project key (optional).")] = "",
    ) -> str:
        """Full trigger / conditions / actions config for an A4J rule."""
        if not rule_id:
            return error_json("rule_id is required")
        client = get_client(ctx)
        path = (
            f"/rest/cb-automation/latest/project/{seg(project)}/rule/{seg(rule_id)}"
            if project
            else f"/rest/cb-automation/latest/rule/{seg(rule_id)}"
        )
        return to_json(await client.rest_get(path))
