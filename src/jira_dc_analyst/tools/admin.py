"""Toolset ``admin`` — Workflows (+ raw XML, transition conditions/validators/post-functions), screens, permission/notification/workflow/field-config/issue-security schemes, groups, roles, licensing, cluster, reindex."""

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
    # Admin configuration (workflows, screens, schemes, users, groups, etc.)
    # =====================================================================

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Workflows", "readOnlyHint": True},
    )
    async def list_workflows(
        ctx: Context,
        search: Annotated[
            str,
            Field(description="Case-insensitive substring filter on workflow name."),
        ] = "",
    ) -> str:
        """List all Jira workflows with step counts and last-updated dates."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_workflows", search=search))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "Get Workflow", "readOnlyHint": True},
    )
    async def get_workflow(
        ctx: Context,
        workflow_name: Annotated[str, Field(description="Workflow name.")],
    ) -> str:
        """Get workflow structure — steps with linked statuses, global actions, transitions."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_workflow", name=workflow_name))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "Get Workflow Transition", "readOnlyHint": True},
    )
    async def get_workflow_transition(
        ctx: Context,
        workflow_name: Annotated[str, Field(description="Workflow name.")],
        transition_id: Annotated[
            str,
            Field(description="Numeric transition action id (e.g. '1' for Create Issue)."),
        ],
    ) -> str:
        """Conditions tree, validators, pre/post-functions with class names and parameters."""
        client = get_client(ctx)
        return to_json(
            await client.sr_action(
                "get_workflow_transition",
                name=workflow_name,
                transitionId=transition_id,
            )
        )

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "Get Workflow XML", "readOnlyHint": True},
    )
    async def get_workflow_xml(
        ctx: Context,
        workflow_name: Annotated[str, Field(description="Workflow name.")],
    ) -> str:
        """Raw OSWorkflow XML — for deep inspection, migration, or diffing."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_workflow_xml", name=workflow_name))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Screens", "readOnlyHint": True},
    )
    async def list_screens(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on screen name.")] = "",
    ) -> str:
        """List all field screens — id, name, description, tab count."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_screens", search=search))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "Get Screen", "readOnlyHint": True},
    )
    async def get_screen(
        ctx: Context,
        screen_id: Annotated[str, Field(description="Numeric screen id.")],
    ) -> str:
        """Screen tabs with their fields (id, name, position)."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_screen", id=screen_id))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Screen Schemes", "readOnlyHint": True},
    )
    async def list_screen_schemes(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on name.")] = "",
    ) -> str:
        """Maps operations (Create/Edit/View) to screens."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_screen_schemes", search=search))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Issue Type Screen Schemes", "readOnlyHint": True},
    )
    async def list_issue_type_screen_schemes(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on name.")] = "",
    ) -> str:
        """Maps issue types to screen schemes."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_issue_type_screen_schemes", search=search))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Permission Schemes", "readOnlyHint": True},
    )
    async def list_permission_schemes(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """List all permission schemes with associated project keys."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_permission_schemes"))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "Get Permission Scheme", "readOnlyHint": True},
    )
    async def get_permission_scheme(
        ctx: Context,
        scheme_id: Annotated[str, Field(description="Permission scheme id.")],
    ) -> str:
        """All permission grants (permission key, grant type, grant value)."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_permission_scheme", id=scheme_id))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Notification Schemes", "readOnlyHint": True},
    )
    async def list_notification_schemes(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """List all notification schemes with associated project keys."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_notification_schemes"))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "Get Notification Scheme", "readOnlyHint": True},
    )
    async def get_notification_scheme(
        ctx: Context,
        scheme_id: Annotated[str, Field(description="Notification scheme id.")],
    ) -> str:
        """All event-to-recipient mappings for the scheme."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_notification_scheme", id=scheme_id))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Workflow Schemes", "readOnlyHint": True},
    )
    async def list_workflow_schemes(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """List all workflow schemes with associated project keys."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_workflow_schemes"))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "Get Workflow Scheme", "readOnlyHint": True},
    )
    async def get_workflow_scheme(
        ctx: Context,
        scheme_id: Annotated[str, Field(description="Workflow scheme id.")],
    ) -> str:
        """Default workflow and issue type → workflow mappings."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_workflow_scheme", id=scheme_id))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "Get Project Admin Config", "readOnlyHint": True},
    )
    async def get_project_config(
        ctx: Context,
        project_key: Annotated[str, Field(description="Project key (e.g. 'HR').")],
    ) -> str:
        """Full project admin view — all assigned schemes, roles with members, components, versions."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_project_config", key=project_key))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Projects (Admin View)", "readOnlyHint": True},
    )
    async def list_projects(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on key or name.")] = "",
    ) -> str:
        """Projects with key, name, lead, category, assigned permission/workflow schemes."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_projects", search=search))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Groups", "readOnlyHint": True},
    )
    async def list_groups(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on group name.")] = "",
    ) -> str:
        """List all groups with member counts."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_groups", search=search))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "Get Group Members", "readOnlyHint": True},
    )
    async def get_group_members(
        ctx: Context,
        group_name: Annotated[str, Field(description="Exact group name.")],
    ) -> str:
        """Group members — username, display name, email, active flag."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_group_members", group=group_name))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Project Roles", "readOnlyHint": True},
    )
    async def list_project_roles(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """All project roles — id, name, description."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_project_roles"))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "Get Project Role Members", "readOnlyHint": True},
    )
    async def get_project_role_members(
        ctx: Context,
        project_key: Annotated[str, Field(description="Project key.")],
        role_id: Annotated[str, Field(description="Role id.")],
    ) -> str:
        """Users and groups assigned to a role in the given project."""
        client = get_client(ctx)
        return to_json(
            await client.sr_action("get_project_role_members", project=project_key, roleId=role_id)
        )

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "Get User (Admin View)", "readOnlyHint": True},
    )
    async def get_user(
        ctx: Context,
        username: Annotated[str, Field(description="Username (preferred for DC).")] = "",
        key: Annotated[str, Field(description="User key.")] = "",
    ) -> str:
        """Display name, email, active, groups, application roles (Software/JSM/Core)."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_user", username=username, key=key))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Application Roles", "readOnlyHint": True},
    )
    async def list_application_roles(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """License tiers with seat usage — critical for capacity audits."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_application_roles"))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Issue Types", "readOnlyHint": True},
    )
    async def list_issue_types(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """All issue types — id, name, description, isSubtask, icon."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_issue_types"))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Issue Type Schemes", "readOnlyHint": True},
    )
    async def list_issue_type_schemes(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on name.")] = "",
    ) -> str:
        """Default issue type, mapped types, associated projects."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_issue_type_schemes", search=search))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Reference Data", "readOnlyHint": True},
    )
    async def list_reference_data(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """All statuses (with categories), priorities, resolutions."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_reference_data"))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Field Configurations", "readOnlyHint": True},
    )
    async def list_field_configurations(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on name.")] = "",
    ) -> str:
        """Field configurations — id, name, isDefault, field count."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_field_configurations", search=search))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "Get Field Configuration", "readOnlyHint": True},
    )
    async def get_field_configuration(
        ctx: Context,
        config_id: Annotated[
            str,
            Field(description="Config id, or 'default' for the default configuration."),
        ],
    ) -> str:
        """Per-field settings: hidden, required, renderer, description override."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_field_configuration", id=config_id))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Field Configuration Schemes", "readOnlyHint": True},
    )
    async def list_field_config_schemes(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on name.")] = "",
    ) -> str:
        """Field-config schemes with associated projects."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_field_config_schemes", search=search))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "Get Field Configuration Scheme", "readOnlyHint": True},
    )
    async def get_field_config_scheme(
        ctx: Context,
        scheme_id: Annotated[str, Field(description="Field config scheme id.")],
    ) -> str:
        """Issue type → field configuration mappings."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_field_config_scheme", id=scheme_id))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Issue Link Types", "readOnlyHint": True},
    )
    async def list_issue_link_types(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """All link types — name, inward/outward descriptions."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_issue_link_types"))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Issue Security Schemes", "readOnlyHint": True},
    )
    async def list_issue_security_schemes(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """All issue security schemes with associated project keys."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_issue_security_schemes"))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "Get Issue Security Scheme", "readOnlyHint": True},
    )
    async def get_issue_security_scheme(
        ctx: Context,
        scheme_id: Annotated[str, Field(description="Issue security scheme id.")],
    ) -> str:
        """All security levels with their access grants (users, groups, roles)."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_issue_security_scheme", id=scheme_id))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "Get Server Info", "readOnlyHint": True},
    )
    async def get_server_info(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """Jira version, build number, base URL, title."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_server_info"))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "Get Application Properties", "readOnlyHint": True},
    )
    async def get_application_properties(
        ctx: Context,
        search: Annotated[str, Field(description="Filter by key or value substring.")] = "",
    ) -> str:
        """Global settings: time tracking, attachment limits, voting, watching, subtasks."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_application_properties", search=search))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Project Categories", "readOnlyHint": True},
    )
    async def list_project_categories(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """Project categories — used to group projects."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_project_categories"))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Event Types", "readOnlyHint": True},
    )
    async def list_event_types(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """All event types — maps event IDs in notification schemes to human-readable names."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_event_types"))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Global Permissions", "readOnlyHint": True},
    )
    async def list_global_permissions(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """Who has SYSTEM_ADMIN, ADMINISTER, USE, BULK_CHANGE, etc."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_global_permissions"))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Shared Filters", "readOnlyHint": True},
    )
    async def list_shared_filters(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on name.")] = "",
    ) -> str:
        """All shared filters — name, JQL, owner, favourite count."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_shared_filters", search=search))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Dashboards", "readOnlyHint": True},
    )
    async def list_dashboards(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on name.")] = "",
    ) -> str:
        """All shared dashboards — name, owner, favourite count, system default."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_dashboards", search=search))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "Get Cluster Info", "readOnlyHint": True},
    )
    async def get_cluster_info(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """DC cluster: is clustered, node count, each node ID/state/IP, current node flag."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_cluster_info", cache=False))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Priority Schemes", "readOnlyHint": True},
    )
    async def list_priority_schemes(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """Priority schemes (Jira 10.x). Error hint if not available."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_priority_schemes"))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "Get Custom Field Admin", "readOnlyHint": True},
    )
    async def get_custom_field(
        ctx: Context,
        field_id: Annotated[
            str,
            Field(description="Custom field id, e.g. 'customfield_10100'."),
        ],
    ) -> str:
        """Custom field with ALL contexts and project/issue-type scope."""
        client = get_client(ctx)
        return to_json(await client.sr_action("get_custom_field", id=field_id))

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "List Custom Field Types", "readOnlyHint": True},
    )
    async def list_custom_field_types(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """Available custom field types — essential for building admin ТЗ."""
        client = get_client(ctx)
        return to_json(await client.sr_action("list_custom_field_types"))

    # =====================================================================
    # Admin additions — my permissions, reindex
    # =====================================================================

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "My Permissions", "readOnlyHint": True},
    )
    async def my_permissions(
        ctx: Context,
        project_key: Annotated[
            str,
            Field(
                description=(
                    "Project key to scope the check. Use together with "
                    "issue_key for per-issue permission decisions."
                )
            ),
        ] = "",
        issue_key: Annotated[
            str,
            Field(description="Issue key for per-issue permission scoping."),
        ] = "",
        permissions: Annotated[
            str,
            Field(
                description=(
                    "Optional comma-separated permission keys to filter, "
                    "e.g. 'EDIT_ISSUES,DELETE_ISSUES'."
                )
            ),
        ] = "",
    ) -> str:
        """Check which permissions the authenticated user has on a project or issue.

        Answers "can user X do Y on project Z" without manually cross-referencing
        permission schemes + roles + groups. Backed by
        ``GET /rest/api/2/mypermissions``. DC returns the full list if
        ``permissions`` is omitted; we pass it through for forward-compat with
        Cloud where it's mandatory.
        """
        params: dict[str, Any] = {}
        if project_key:
            params["projectKey"] = project_key
        if issue_key:
            params["issueKey"] = issue_key
        if permissions:
            params["permissions"] = permissions
        client = get_client(ctx)
        try:
            return to_json(await client.rest_get("/rest/api/2/mypermissions", **params))
        except AnalystError as exc:
            return error_json(f"my_permissions failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:admin"},
        annotations={"title": "Reindex Status", "readOnlyHint": True},
    )
    async def get_reindex_status(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """Get the current or last Jira reindex progress — is indexing running, stuck, or done.

        Diagnostic for "search results are stale" or "custom fields not
        showing up". Backed by ``GET /rest/api/2/reindex``.

        Returns a ``no_reindex_recorded`` sentinel instead of a raw 404 when
        the instance has never reindexed, so callers can tell "never
        reindexed" from "permission denied".
        """
        client = get_client(ctx)
        try:
            return to_json(await client.rest_get("/rest/api/2/reindex", cache=False))
        except AnalystError as exc:
            if exc.status == 404:
                return to_json(
                    {
                        "status": "no_reindex_recorded",
                        "note": (
                            "/rest/api/2/reindex returned 404 — this instance "
                            "has no stored reindex progress (likely never "
                            "reindexed, or progress was cleared)."
                        ),
                    }
                )
            return error_json(f"get_reindex_status failed: {exc}", status=exc.status)
