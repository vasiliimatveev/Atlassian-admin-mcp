"""Toolset ``properties`` — Entity properties on projects, issues and users."""

import logging
from collections.abc import Callable
from typing import Annotated, Any

from fastmcp import Context
from pydantic import Field

from ..client import JiraError
from ..util import error_json, get_client, seg, to_json

logger = logging.getLogger(__name__)


def register(tool: Callable[..., Any]) -> None:  # noqa: C901 — flat list of thin wrappers
    # =====================================================================
    # Entity properties — the "JSON blob" storage that many plugins use
    # instead of their own REST (JXL, Jira Automation, ScriptRunner,
    # assorted integrations). Jira's own REST exposes per-scope CRUD, so
    # we get read access to all of them through a tiny surface.
    #
    #   * Project:  GET /rest/api/2/project/{keyOrId}/properties
    #   * Issue:    GET /rest/api/2/issue/{keyOrId}/properties
    #   * User:     GET /rest/api/2/user/properties?username=X  (DC)
    #
    # A GET on the collection path returns the list of property *keys*;
    # a GET on ``/{collection}/{key}`` returns the JSON value.
    # Auth: whatever the user has on the scope (Browse Project / Browse
    # Issue / the user themselves).  See
    # https://developer.atlassian.com/server/jira/platform/entity-properties/
    # =====================================================================

    @tool(
        tags={"read", "toolset:properties"},
        annotations={"title": "List Project Properties", "readOnlyHint": True},
    )
    async def list_project_properties(
        ctx: Context,
        project_key: Annotated[str, Field(description="Project key or id.")],
    ) -> str:
        """Keys of all entity properties on a project — the first step when
        discovering plugin-stored configuration (e.g. JXL sheets,
        Automation-for-Jira rules, custom integration state). Vendors don't
        publish their own key names; enumerate here first, then read with
        ``get_project_property``."""
        client = get_client(ctx)
        try:
            return to_json(
                await client.rest_get(f"/rest/api/2/project/{seg(project_key)}/properties")
            )
        except JiraError as exc:
            return error_json(f"list_project_properties failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:properties"},
        annotations={"title": "Get Project Property", "readOnlyHint": True},
    )
    async def get_project_property(
        ctx: Context,
        project_key: Annotated[str, Field(description="Project key or id.")],
        property_key: Annotated[
            str, Field(description="Property key (from list_project_properties).")
        ],
    ) -> str:
        """Full JSON value of a single project property. The schema inside
        is vendor-private (JXL, Automation, etc. each define their own)
        and may change between plugin versions — treat as opaque."""
        client = get_client(ctx)
        try:
            return to_json(
                await client.rest_get(
                    f"/rest/api/2/project/{seg(project_key)}/properties/{seg(property_key)}"
                )
            )
        except JiraError as exc:
            return error_json(f"get_project_property failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:properties"},
        annotations={"title": "List Issue Properties", "readOnlyHint": True},
    )
    async def list_issue_properties(
        ctx: Context,
        issue_key: Annotated[str, Field(description="Issue key or id.")],
    ) -> str:
        """Keys of all entity properties on an issue. Useful for debugging
        per-issue plugin state (e.g. assorted scripting caches, sprint
        metadata written by agile plugins)."""
        client = get_client(ctx)
        try:
            return to_json(await client.rest_get(f"/rest/api/2/issue/{seg(issue_key)}/properties"))
        except JiraError as exc:
            return error_json(f"list_issue_properties failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:properties"},
        annotations={"title": "Get Issue Property", "readOnlyHint": True},
    )
    async def get_issue_property(
        ctx: Context,
        issue_key: Annotated[str, Field(description="Issue key or id.")],
        property_key: Annotated[str, Field(description="Property key.")],
    ) -> str:
        """Full JSON of one issue property."""
        client = get_client(ctx)
        try:
            return to_json(
                await client.rest_get(
                    f"/rest/api/2/issue/{seg(issue_key)}/properties/{seg(property_key)}"
                )
            )
        except JiraError as exc:
            return error_json(f"get_issue_property failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:properties"},
        annotations={"title": "List User Properties", "readOnlyHint": True},
    )
    async def list_user_properties(
        ctx: Context,
        username: Annotated[
            str,
            Field(
                description=(
                    "DC username. User-properties endpoint is DC-only — "
                    "Cloud uses accountId instead."
                )
            ),
        ],
    ) -> str:
        """Keys of all per-user properties. Some plugins store personal
        preferences there (e.g. JXL may keep private sheets here rather
        than on a project)."""
        if not username:
            return error_json("username is required")
        client = get_client(ctx)
        try:
            return to_json(await client.rest_get("/rest/api/2/user/properties", username=username))
        except JiraError as exc:
            return error_json(f"list_user_properties failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:properties"},
        annotations={"title": "Get User Property", "readOnlyHint": True},
    )
    async def get_user_property(
        ctx: Context,
        username: Annotated[str, Field(description="DC username.")],
        property_key: Annotated[str, Field(description="Property key.")],
    ) -> str:
        """Full JSON of one user property."""
        if not username:
            return error_json("username is required")
        client = get_client(ctx)
        try:
            return to_json(
                await client.rest_get(
                    f"/rest/api/2/user/properties/{seg(property_key)}",
                    username=username,
                )
            )
        except JiraError as exc:
            return error_json(f"get_user_property failed: {exc}", status=exc.status)
