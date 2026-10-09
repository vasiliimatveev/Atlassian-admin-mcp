"""Server assembly: settings → FastMCP instance with the enabled toolsets."""

from __future__ import annotations

import asyncio
import contextlib
import functools
import json
from collections.abc import AsyncIterator, Callable
from typing import Annotated, Any

import httpx
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import TextContent
from pydantic import Field

from . import __version__
from .client import AnalystClient, AnalystError
from .config import Settings
from .tools import MODULES
from .toolsets import TOOLSETS, resolve_toolsets
from .util import InvalidArgument, get_client, set_json_indent, to_json

INSTRUCTIONS = """\
Read-only inspection of a Jira Data Center instance for administrators:
workflows, schemes, screens, custom fields, users/groups/roles, licensing,
plugins (ScriptRunner, JMWE, Structure, Assets, Automation, SLA, Time in
Status, Email This Issue), Git/DVCS integration, audit and system logs.
No tool changes anything in Jira.

Start with jira_analyst_status if calls fail: it checks connectivity, the
Groovy endpoint and which toolsets are enabled. List tools return ids and
names; use the matching get_* tool for full detail."""

READ_ONLY_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
}


def classify(status: int | None, via_groovy: bool, settings: Settings) -> dict[str, Any]:
    """Map an HTTP status to a stable ``kind`` an agent can branch on, plus a hint."""
    if status is None:
        return {
            "kind": "unreachable",
            "retryable": True,
            "hint": f"Check JIRA_URL ({settings.url}), network/proxy and JIRA_SSL_VERIFY.",
        }
    if status == 401:
        return {
            "kind": "auth_failed",
            "retryable": False,
            "hint": "Check JIRA_PERSONAL_TOKEN or username/token.",
        }
    if via_groovy and status == 404:
        return {
            "kind": "groovy_endpoint_missing",
            "retryable": False,
            "hint": f"Install groovy/admin_analyst.groovy as a ScriptRunner REST endpoint "
            f"at {settings.sr_path}, or set JIRA_ANALYST_SR_PATH. Tools that do not "
            "need the endpoint still work.",
        }
    if via_groovy and status == 403:
        return {
            "kind": "groovy_forbidden",
            "retryable": False,
            "hint": "The user is not in ALLOWED_GROUPS of admin_analyst.groovy "
            "(default: jira-administrators).",
        }
    if status == 403:
        return {
            "kind": "forbidden",
            "retryable": False,
            "hint": "This call needs Jira admin or plugin-specific permission.",
        }
    if status == 404:
        return {
            "kind": "not_found",
            "retryable": False,
            "hint": "Wrong id/key, or the plugin behind this REST API is not installed. "
            "Use the matching list_* tool to find valid ids.",
        }
    if status == 413:
        return {
            "kind": "too_large",
            "retryable": False,
            "hint": "Narrow the request (filters, smaller page) or use a thumbnail/URL.",
        }
    if status in (429, 502, 503, 504):
        return {
            "kind": "jira_busy",
            "retryable": True,
            "hint": "Jira is overloaded or restarting; retry later.",
        }
    if status >= 500:
        return {
            "kind": "jira_error",
            "retryable": False,
            "hint": "Server-side failure; see 'detail'.",
        }
    return {"kind": "bad_request", "retryable": False, "hint": "Check the arguments."}


def describe_error(exc: AnalystError, settings: Settings) -> dict[str, Any]:
    """Structured, actionable description of a failed Jira call."""
    via_groovy = bool(exc.url and exc.url.split("?")[0].endswith(settings.sr_path))
    payload: dict[str, Any] = {"error": str(exc), "status": exc.status}
    payload.update(classify(exc.status, via_groovy, settings))
    if exc.body:
        payload["detail"] = exc.body[:300]
    return payload


_MAX_ERROR_PAYLOAD = 20_000


def _as_error(text: str, settings: Settings) -> str | None:
    """Return an enriched error payload if ``text`` is one.

    Convention shared with the Groovy endpoint: a JSON object with a
    top-level ``error`` key is a failure. Only small objects are parsed —
    real data is never mistaken for an error and never parsed twice.
    """
    if len(text) > _MAX_ERROR_PAYLOAD or not text.lstrip().startswith("{") or '"error"' not in text:
        return None
    try:
        payload = json.loads(text)
    except ValueError:
        return None
    if not isinstance(payload, dict) or "error" not in payload:
        return None
    if "kind" not in payload:
        status = payload.get("status")
        if isinstance(status, int):
            payload.update(classify(status, False, settings))
        else:
            payload.setdefault("kind", "failed")
    return to_json(payload)


def _truncate(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    return to_json(
        {
            "truncated": True,
            "totalChars": len(text),
            "returnedChars": limit,
            "hint": "Response exceeded JIRA_ANALYST_MAX_RESPONSE_CHARS. Narrow it with "
            "search/project filters or fetch single objects with get_* tools.",
            "partial": text[:limit],
        }
    )


def _guard(fn: Callable[..., Any], settings: Settings) -> Callable[..., Any]:
    """Uniform result handling for every tool.

    * failures always surface as ``isError`` results with a JSON body
      ``{error, kind, status, hint, retryable}`` — including tools that
      return an ``{"error": ...}`` payload instead of raising;
    * oversized text results are cut with an explicit ``truncated`` marker.
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            result = await fn(*args, **kwargs)
        except AnalystError as exc:
            raise ToolError(to_json(describe_error(exc, settings))) from exc
        except InvalidArgument as exc:
            raise ToolError(
                to_json({"error": str(exc), "kind": "invalid_argument", "retryable": False})
            ) from exc
        if isinstance(result, str):
            error = _as_error(result, settings)
            if error is not None:
                raise ToolError(error)
            return _truncate(result, settings.max_response_chars)
        if isinstance(result, list) and len(result) == 1 and isinstance(result[0], TextContent):
            error = _as_error(result[0].text, settings)
            if error is not None:
                raise ToolError(error)
        return result

    return wrapper


def create_server(
    settings: Settings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastMCP:
    """Build the MCP server. ``transport`` lets tests swap in a mock HTTP layer."""
    set_json_indent(settings.json_indent)
    enabled = resolve_toolsets(settings.toolsets)

    @contextlib.asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        client = AnalystClient(settings, transport=transport)
        try:
            yield {"client": client}
        finally:
            await client.aclose()

    mcp = FastMCP(
        "jira-dc-analyst",
        instructions=INSTRUCTIONS,
        version=__version__,
        lifespan=lifespan,
    )

    def tool(*, tags: set[str], annotations: dict[str, Any], **kwargs: Any) -> Callable:
        toolset = next(t.removeprefix("toolset:") for t in tags if t.startswith("toolset:"))
        if toolset not in TOOLSETS:
            raise ValueError(f"unknown toolset tag {toolset!r}")

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            if toolset in enabled:
                mcp.tool(
                    name=f"jira_{fn.__name__}",
                    tags=set(tags),
                    annotations={**annotations, **READ_ONLY_ANNOTATIONS},
                    # Tools return JSON text; without this FastMCP would also
                    # send it as structuredContent, doubling every response.
                    output_schema=None,
                    **kwargs,
                )(_guard(fn, settings))
            return fn

        return decorator

    for module in MODULES:
        module.register(tool)
    _register_status_tool(mcp, settings, enabled)
    return mcp


def _register_status_tool(mcp: FastMCP, settings: Settings, enabled: set[str]) -> None:
    @mcp.tool(
        name="jira_analyst_status",
        tags={"read", "toolset:core"},
        annotations={"title": "Analyst Status / Self-check", **READ_ONLY_ANNOTATIONS},
        output_schema=None,
    )
    async def analyst_status(
        ctx: Context,
        clear_cache: Annotated[
            bool, Field(description="Drop cached responses before checking.")
        ] = False,
    ) -> str:
        """Check connectivity, auth, the Groovy endpoint and enabled toolsets.

        Run this first when other tools fail: it tells apart a wrong URL, a bad
        token, a missing or outdated Groovy endpoint, and a missing permission.
        """
        client = get_client(ctx)
        if clear_cache:
            client.clear_cache()
        server_info, me, ping = await asyncio.gather(
            client.rest_get("/rest/api/2/serverInfo", cache=False),
            client.rest_get("/rest/api/2/myself", cache=False),
            client.sr_action("ping", cache=False),
            return_exceptions=True,
        )

        def outcome(result: Any) -> Any:
            if isinstance(result, AnalystError):
                return {"ok": False, **describe_error(result, settings)}
            if isinstance(result, BaseException):
                return {"ok": False, "error": repr(result)}
            return None

        report: dict[str, Any] = {"server": __version__, "jiraUrl": settings.url}
        report["jira"] = outcome(server_info) or {
            "ok": True,
            "version": server_info.get("version"),
            "deploymentType": server_info.get("deploymentType"),
            "baseUrl": server_info.get("baseUrl"),
        }
        report["user"] = outcome(me) or {
            "ok": True,
            "name": me.get("name"),
            "displayName": me.get("displayName"),
        }
        groovy = outcome(ping)
        if groovy is None:
            if isinstance(ping, dict) and ping.get("ok"):
                groovy = {"ok": True, **{k: v for k, v in ping.items() if k != "ok"}}
            else:
                groovy = {
                    "ok": True,
                    "warning": "Endpoint answered but has no 'ping' action — it is an "
                    "older admin_analyst.groovy; redeploy the bundled version.",
                }
        report["groovyEndpoint"] = {"path": settings.sr_path, **groovy}
        report["toolsets"] = {
            name: {"enabled": name in enabled, "requires": t.requires}
            for name, t in TOOLSETS.items()
        }
        report["cache"] = client.cache_stats()
        return to_json(report)
