"""Toolset ``assets`` — Insight / Assets CMDB: schemas, object types, AQL, imports."""

import logging
from collections.abc import Callable
from typing import Annotated, Any

from fastmcp import Context
from pydantic import Field

from ..util import error_json, get_client, to_json

logger = logging.getLogger(__name__)

MAX_AQL_LENGTH = 2000


def register(tool: Callable[..., Any]) -> None:  # noqa: C901 — flat list of thin wrappers
    # =====================================================================
    # Insight / Assets (CMDB)
    # =====================================================================

    @tool(
        tags={"read", "toolset:assets"},
        annotations={"title": "List Asset Schemas", "readOnlyHint": True},
    )
    async def list_object_schemas(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """All Insight/Assets object schemas."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_object_schemas"))

    @tool(
        tags={"read", "toolset:assets"},
        annotations={"title": "Get Asset Schema", "readOnlyHint": True},
    )
    async def get_object_schema(
        ctx: Context,
        schema_id: Annotated[str, Field(description="Numeric schema id.")],
    ) -> str:
        """Schema metadata + object-type hierarchy."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_object_schema", id=schema_id))

    @tool(
        tags={"read", "toolset:assets"},
        annotations={"title": "List Asset Object Types", "readOnlyHint": True},
    )
    async def list_object_types(
        ctx: Context,
        schema_id: Annotated[str, Field(description="Schema id.")],
    ) -> str:
        """Object types in the schema — name, parent, object count, abstract flag."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_object_types", schemaId=schema_id))

    @tool(
        tags={"read", "toolset:assets"},
        annotations={"title": "Get Object Type Attributes", "readOnlyHint": True},
    )
    async def get_object_type_attributes(
        ctx: Context,
        object_type_id: Annotated[str, Field(description="Object type id.")],
    ) -> str:
        """All attributes — data type, required, cardinality, reference type for links."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_object_type_attributes", id=object_type_id))

    @tool(
        tags={"read", "toolset:assets"},
        annotations={"title": "AQL Search", "readOnlyHint": True},
    )
    async def aql_search(
        ctx: Context,
        aql: Annotated[
            str,
            Field(
                description=(
                    "AQL expression, e.g. 'objectType = Server', 'Name like \"prod\"', 'Status = Active'."
                )
            ),
        ],
        schema: Annotated[str, Field(description="Optional schema id/key to limit scope.")] = "",
        max_results: Annotated[str, Field(description="Max results (1..50). Default 25.")] = "25",
    ) -> str:
        """Search Assets objects using AQL. Returns object key, label, type."""
        if not aql.strip():
            return error_json("aql is required")
        if len(aql) > MAX_AQL_LENGTH:
            return error_json(f"aql too long: {len(aql)} > {MAX_AQL_LENGTH}")
        try:
            mr = max(1, min(int(max_results), 50))
        except (TypeError, ValueError):
            mr = 25
        client = get_client(ctx)
        return to_json(
            await client.sr_action("aql_search", schema=schema, aql=aql, maxResults=str(mr))
        )

    @tool(
        tags={"read", "toolset:assets"},
        annotations={"title": "Get Asset Object", "readOnlyHint": True},
    )
    async def get_asset_object(
        ctx: Context,
        object_id: Annotated[str, Field(description="Numeric object id.")],
    ) -> str:
        """All attributes with values, referenced objects, object type, timestamps."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_asset_object", id=object_id))

    @tool(
        tags={"read", "toolset:assets"},
        annotations={"title": "List Reference Types", "readOnlyHint": True},
    )
    async def list_reference_types(
        ctx: Context,
        schema_id: Annotated[str, Field(description="Schema id.")],
    ) -> str:
        """Relationship kinds between objects (Dependency, Installed on, Uses, …)."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_reference_types", schemaId=schema_id))

    @tool(
        tags={"read", "toolset:assets"},
        annotations={"title": "List Asset Status Types", "readOnlyHint": True},
    )
    async def list_status_types(
        ctx: Context,
        schema_id: Annotated[str, Field(description="Schema id.")],
    ) -> str:
        """Object lifecycle states (Active, Inactive, Pending) with categories."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_status_types", schemaId=schema_id))

    @tool(
        tags={"read", "toolset:assets"},
        annotations={"title": "List Asset Import Configs", "readOnlyHint": True},
    )
    async def list_import_configs(
        ctx: Context,
        schema_id: Annotated[str, Field(description="Schema id.")],
    ) -> str:
        """LDAP/CSV/DB syncs with cron schedules and last execution — where CMDB data comes from."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_import_configs", schemaId=schema_id))

    @tool(
        tags={"read", "toolset:assets"},
        annotations={"title": "Get Asset Connected Tickets", "readOnlyHint": True},
    )
    async def get_object_connected_tickets(
        ctx: Context,
        object_id: Annotated[str, Field(description="Asset object id.")],
    ) -> str:
        """Jira issues connected to an Assets object — CMDB ↔ issue relationships."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_object_connected_tickets", id=object_id))
