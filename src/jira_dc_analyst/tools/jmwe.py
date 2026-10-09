"""Toolset ``jmwe`` — JMWE event-based and shared actions."""

import logging
from collections.abc import Callable
from typing import Annotated, Any

from fastmcp import Context
from pydantic import Field

from ..util import get_client, to_json

logger = logging.getLogger(__name__)


def register(tool: Callable[..., Any]) -> None:
    # =====================================================================
    # JMWE
    # =====================================================================

    @tool(
        tags={"read", "toolset:jmwe"},
        annotations={"title": "List JMWE Event Actions", "readOnlyHint": True},
    )
    async def list_jmwe_event_actions(
        ctx: Context,
        project: Annotated[str, Field(description="Optional project key filter.")] = "",
    ) -> str:
        """JMWE event-based actions — trigger event, project scope, JQL, condition, post-functions."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_jmwe_event_actions", project=project))

    @tool(
        tags={"read", "toolset:jmwe"},
        annotations={"title": "Get JMWE Event Action", "readOnlyHint": True},
    )
    async def get_jmwe_event_action(
        ctx: Context,
        action_id: Annotated[str, Field(description="Event action UUID.")],
    ) -> str:
        """Full config — trigger, scope, JQL, Groovy condition, post-functions with classes + JSON."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_jmwe_event_action", id=action_id))

    @tool(
        tags={"read", "toolset:jmwe"},
        annotations={"title": "List JMWE Shared Actions", "readOnlyHint": True},
    )
    async def list_jmwe_shared_actions(
        ctx: Context,
        type: Annotated[
            str,
            Field(description="Filter: 'post-function', 'condition', or 'validator' (substring)."),
        ] = "",
    ) -> str:
        """Reusable post-functions, conditions, validators referenced from workflow transitions."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_jmwe_shared_actions", type=type))

    @tool(
        tags={"read", "toolset:jmwe"},
        annotations={"title": "Get JMWE Shared Action", "readOnlyHint": True},
    )
    async def get_jmwe_shared_action(
        ctx: Context,
        action_id: Annotated[str, Field(description="Shared action id.")],
    ) -> str:
        """All getters from the AO entity — config JSON, inline Groovy, run-as user."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_jmwe_shared_action", id=action_id))
