"""Toolset ``integrations`` — UPM plugins and modules, webhooks, application links, dark features."""

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
    # Integrations surface — plugins, webhooks, applinks, dark features
    # =====================================================================

    # UPM requires an explicit vendor-specific Accept header or returns HTML.
    # https://developer.atlassian.com/platform/marketplace/registering-apps/
    _UPM_ACCEPT_LIST = "application/vnd.atl.plugins.installed+json"
    _UPM_ACCEPT_PLUGIN = "application/vnd.atl.plugins.plugin+json"

    @tool(
        tags={"read", "toolset:integrations"},
        annotations={"title": "List Installed Plugins (UPM)", "readOnlyHint": True},
    )
    async def list_plugins(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """Installed plugins via Universal Plugin Manager (SYS_ADMIN required)."""
        client = get_client(ctx)
        try:
            return to_json(await client.rest_get("/rest/plugins/1.0/", accept=_UPM_ACCEPT_LIST))
        except JiraError as exc:
            return error_json(f"list_plugins failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:integrations"},
        annotations={"title": "Get Plugin (UPM)", "readOnlyHint": True},
    )
    async def get_plugin(
        ctx: Context,
        plugin_key: Annotated[
            str,
            Field(
                description=("Plugin key, e.g. 'com.atlassian.jira.plugins.jira-importers-plugin'.")
            ),
        ],
    ) -> str:
        """Single plugin details — UPM ``/rest/plugins/1.0/{key}-key``."""
        client = get_client(ctx)
        try:
            return to_json(
                await client.rest_get(
                    f"/rest/plugins/1.0/{seg(plugin_key)}-key",
                    accept=_UPM_ACCEPT_PLUGIN,
                )
            )
        except JiraError as exc:
            return error_json(f"get_plugin failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:integrations"},
        annotations={"title": "Get Plugin Modules (UPM)", "readOnlyHint": True},
    )
    async def get_plugin_modules(
        ctx: Context,
        plugin_key: Annotated[str, Field(description="Plugin key.")],
    ) -> str:
        """Enabled/disabled modules for a plugin (completeKey, type, name)."""
        client = get_client(ctx)
        try:
            return to_json(
                await client.rest_get(
                    f"/rest/plugins/1.0/{seg(plugin_key)}-key/modules",
                    accept=_UPM_ACCEPT_PLUGIN,
                )
            )
        except JiraError as exc:
            return error_json(f"get_plugin_modules failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:integrations"},
        annotations={"title": "List Webhooks", "readOnlyHint": True},
    )
    async def list_webhooks(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """List instance webhooks.

        Jira ≤ 9.x exposes them at ``/rest/webhooks/1.0/webhook``; Jira ≥ 10.x
        moved the endpoint to ``/rest/jira-webhook/1.0/webhooks``. We try the
        modern path first and fall back to the legacy one, so the tool works
        across supported DC versions. Jira Administrators permission required.
        """
        client = get_client(ctx)
        paths = ("/rest/jira-webhook/1.0/webhooks", "/rest/webhooks/1.0/webhook")
        last_err: JiraError | None = None
        for path in paths:
            try:
                return to_json(await client.rest_get(path))
            except JiraError as exc:
                last_err = exc
                if exc.status in (404, 405):
                    continue
                return error_json(f"list_webhooks failed on {path}: {exc}", status=exc.status)
        return error_json(
            "list_webhooks: neither the v10+ nor the legacy webhook endpoint "
            "responded on this instance",
            status=last_err.status if last_err else None,
        )

    @tool(
        tags={"read", "toolset:integrations"},
        annotations={"title": "List Application Links", "readOnlyHint": True},
    )
    async def list_application_links(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """Application links to Confluence/Bitbucket/other (admin-only).

        Uses ``/rest/applinks/3.0/applicationlink`` and forces
        ``Accept: application/json`` — the applinks service prefers XML
        by default and will return XML if the client doesn't request JSON.
        """
        client = get_client(ctx)
        try:
            return to_json(
                await client.rest_get(
                    "/rest/applinks/3.0/applicationlink",
                    accept="application/json",
                )
            )
        except JiraError as exc:
            return error_json(f"list_application_links failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:integrations"},
        annotations={"title": "List Dark Features (best-effort)", "readOnlyHint": True},
    )
    async def list_dark_features(
        ctx: Context,
        random_string: Annotated[
            str,
            Field(
                description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."
            ),
        ] = "",
    ) -> str:
        """Dark-features toggles via ``/rest/internal/1.0/darkFeatures``.

        This is an **internal/private** Atlassian API — the closest thing
        DC exposes for a feature-flags overview. It's read-only and stable
        enough for audits, but Atlassian may change it without notice.
        """
        client = get_client(ctx)
        try:
            return to_json(await client.rest_get("/rest/internal/1.0/darkFeatures"))
        except JiraError as exc:
            return error_json(
                "list_dark_features failed — /rest/internal/1.0/darkFeatures "
                "is a private API and may be unavailable on this instance",
                status=exc.status,
                detail=str(exc),
            )
