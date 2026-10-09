"""Toolset ``structure`` — ALM Works Structure + Structure.Gantt."""

import logging
from collections.abc import Callable
from typing import Annotated, Any

from fastmcp import Context
from pydantic import Field

from ..client import AnalystError
from ..util import error_json, get_client, seg, to_json

logger = logging.getLogger(__name__)


def register(tool: Callable[..., Any]) -> None:
    # =====================================================================
    # Structure (ALM Works) + Gantt
    # =====================================================================

    @tool(
        tags={"read", "toolset:structure"},
        annotations={"title": "List Structures", "readOnlyHint": True},
    )
    async def list_structures(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on name.")] = "",
    ) -> str:
        """Structure plugin hierarchies — id, name, description, owner, archived state."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_structures", search=search))

    @tool(
        tags={"read", "toolset:structure"},
        annotations={"title": "Get Structure", "readOnlyHint": True},
    )
    async def get_structure(
        ctx: Context,
        structure_id: Annotated[str, Field(description="Structure id.")],
    ) -> str:
        """Name, description, owner, row count, generator configuration."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_structure", id=structure_id))

    @tool(
        tags={"read", "toolset:structure"},
        annotations={"title": "List Structure Views", "readOnlyHint": True},
    )
    async def list_structure_views(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on name.")] = "",
    ) -> str:
        """Structure views — id, name, owner, shared, column count."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_structure_views", search=search))

    @tool(
        tags={"read", "toolset:structure"},
        annotations={"title": "Get Structure View", "readOnlyHint": True},
    )
    async def get_structure_view(
        ctx: Context,
        view_id: Annotated[str, Field(description="View id.")],
    ) -> str:
        """FULL column config — types, parameters, resolved field names, display modes."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_structure_view", id=view_id))

    @tool(
        tags={"read", "toolset:structure"},
        annotations={"title": "Get Gantt Config", "readOnlyHint": True},
    )
    async def get_gantt_config(
        ctx: Context,
        structure_id: Annotated[str, Field(description="Structure id.")],
    ) -> str:
        """Gantt config — date fields, progress, dependencies, calendar, leveling, baseline."""
        client = get_client(ctx)
        try:
            return to_json(
                await client.rest_get(
                    f"/rest/structure-gantt/1.0/configuration/{seg(structure_id)}"
                )
            )
        except AnalystError as exc:
            return error_json(
                f"Cannot read Gantt config for structure {structure_id}",
                detail=str(exc),
            )

    @tool(
        tags={"read", "toolset:structure"},
        annotations={"title": "Get Gantt Schedule", "readOnlyHint": True},
    )
    async def get_gantt_schedule(
        ctx: Context,
        structure_id: Annotated[str, Field(description="Structure id.")],
    ) -> str:
        """Calculated dates, critical path, dependencies, baselines."""
        client = get_client(ctx)
        try:
            return to_json(
                await client.rest_get(f"/rest/structure-gantt/1.0/schedule/{seg(structure_id)}")
            )
        except AnalystError as exc:
            return error_json(
                f"Cannot read Gantt schedule for structure {structure_id}",
                detail=str(exc),
            )

    @tool(
        tags={"read", "toolset:structure"},
        annotations={"title": "Get Gantt Calendar", "readOnlyHint": True},
    )
    async def get_gantt_calendar(
        ctx: Context,
        structure_id: Annotated[str, Field(description="Structure id.")],
    ) -> str:
        """Working days, holidays, work hours."""
        client = get_client(ctx)
        try:
            return to_json(
                await client.rest_get(f"/rest/structure-gantt/1.0/calendar/{seg(structure_id)}")
            )
        except AnalystError as exc:
            return error_json(
                f"Cannot read Gantt calendar for structure {structure_id}",
                detail=str(exc),
            )
