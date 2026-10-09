"""Issue-level access guard driven by a JQL restriction.

When enabled, every Jira request made by a tool is checked here *before* it
is sent — the client has a single HTTP choke point, so no tool can bypass it:

* JQL parameters become ``(<guard>) AND (<jql>) [ORDER BY …]``;
* an issue key or id in the path or query is first verified with
  ``(<guard>) AND issuekey in (…)`` — every reference must come back;
* attachments are only reachable after their issue was verified in the same
  tool call (metadata *and* file download);
* only an explicit allow-list of endpoints and query parameters is accepted;
  everything else — the Groovy endpoint included — is denied;
* outside a tool call only ``/myself`` and ``/serverInfo`` are allowed;
* any failure while checking denies the request.

The guard JQL comes from ``JIRA_GUARD_JQL`` and/or a per-request HTTP header
(``JIRA_GUARD_HEADER``, e.g. ``x-jira-guard-jql`` injected by LiteLLM).
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from .config import Settings
from .jql import GuardDenied, combine, is_numeric_id, parse_issue_ref, validate_guard

# Tools that can be fully confined by JQL. Everything else is hidden in guard mode.
GUARDED_TOOLS = frozenset(
    {
        "jira_get_issue_votes",
        "jira_get_issue_remotelinks",
        "jira_get_attachment_content",
        "jira_get_attachment_thumbnail",
        "jira_list_issue_properties",
        "jira_get_issue_property",
        "jira_get_issue_dev_summary",
        "jira_get_issue_dev_detail",
        "jira_list_gij_issue_commits",
        "jira_list_gij_issue_branches",
        "jira_search_sla_status",
        "jira_get_issue_time_in_status",
        "jira_search_time_in_status",
        "jira_search_jeti_audit_log",
        "jira_get_jeti_audit_count",
    }
)

ALWAYS_ALLOWED = frozenset({"/rest/api/2/myself", "/rest/api/2/serverInfo"})
SEARCH_PATH = "/rest/api/2/search"


@dataclass
class CallGuard:
    """Guard state for one tool call."""

    jql: str
    verified: set[str] = field(default_factory=set)  # normalised keys and ids
    attachments: set[str] = field(default_factory=set)  # released attachment ids


CURRENT: ContextVar[CallGuard | None] = ContextVar("jira_guard_call", default=None)


def resolve_call_guard(settings: Settings) -> CallGuard:
    """Build the guard for the current tool call, or refuse the call."""
    parts: list[str] = []
    if settings.guard_jql:
        parts.append(validate_guard(settings.guard_jql))
    if settings.guard_header:
        parts.append(validate_guard(_header_value(settings.guard_header)))
    if not parts:
        raise GuardDenied("guard is enabled but no guard JQL is configured")
    jql = parts[0] if len(parts) == 1 else " AND ".join(f"({p})" for p in parts)
    return CallGuard(jql=jql)


def _header_value(name: str) -> str:
    from fastmcp.server.dependencies import get_http_request

    try:
        request = get_http_request()
    except RuntimeError as exc:
        raise GuardDenied(f"guard header {name!r} is required; call is not over HTTP") from exc
    # X-Atlassian-* headers re-target or re-authenticate requests in other
    # Atlassian MCP servers; refuse them outright rather than ignore them.
    for header in request.headers:
        if header.lower().startswith("x-atlassian-"):
            raise GuardDenied(f"header {header!r} is not allowed while the guard is on")
    values = request.headers.getlist(name)
    if not values:
        raise GuardDenied(f"guard header {name!r} is missing")
    if len(values) > 1:
        raise GuardDenied(f"guard header {name!r} was sent more than once")
    if not values[0].strip():
        raise GuardDenied(f"guard header {name!r} is empty")
    return values[0]


# ---------------------------------------------------------------------- rules

Verifier = Callable[[list[str]], Awaitable[None]]
Rule = Callable[[re.Match[str], dict[str, str], CallGuard, Verifier], Awaitable[dict[str, str]]]


def _only(params: dict[str, str], allowed: set[str]) -> None:
    extra = set(params) - allowed
    if extra:
        raise GuardDenied(f"query parameters not allowed under the guard: {sorted(extra)}")


def _required(params: dict[str, str], name: str) -> str:
    value = params.get(name, "")
    if not value:
        raise GuardDenied(f"'{name}' is required while the guard is on")
    return value


async def _issue_path(m, params, call, verify):
    _only(params, {"fields", "expand", "globalId"})
    await verify([m["ref"]])
    return params


async def _attachment_meta(m, params, call, verify):
    _only(params, set())
    if m["id"] not in call.attachments:
        raise GuardDenied(
            f"attachment {m['id']} is not released: pass issue_key so its issue is checked first"
        )
    return params


async def _dev_status(m, params, call, verify):
    _only(params, {"issueId", "applicationType", "dataType"})
    await verify([_required(params, "issueId")])
    return params


async def _gij_commits(m, params, call, verify):
    _only(params, {"showfiles"})
    await verify([m["ref"]])
    return params


async def _gij_branches(m, params, call, verify):
    _only(params, {"key"})
    await verify([_required(params, "key")])
    return params


async def _sla_search(m, params, call, verify):
    _only(params, {"jql", "startAt", "maxResults"})
    return {**params, "jql": combine(call.jql, _required(params, "jql"))}


async def _tis_issue(m, params, call, verify):
    _only(params, {"issueKey", "columnsBy", "viewFormat", "calendar"})
    await verify([_required(params, "issueKey")])
    return params


async def _tis_list(m, params, call, verify):
    _only(
        params,
        {
            "filterType",
            "customjql",
            "outputType",
            "columnsBy",
            "pageSize",
            "viewFormat",
            "nextPageToken",
            "calendar",
        },
    )
    if params.get("filterType") != "customjql":
        raise GuardDenied("only filterType=customjql is allowed while the guard is on")
    return {**params, "customjql": combine(call.jql, _required(params, "customjql"))}


async def _jeti(m, params, call, verify):
    _only(params, {"issueKey", "recipient", "template", "from", "to", "limit"})
    await verify([_required(params, "issueKey")])
    return params


_REF = r"(?P<ref>[^/]+)"
RULES: list[tuple[re.Pattern[str], Rule]] = [
    (
        re.compile(rf"/rest/api/2/issue/{_REF}(?:/votes|/remotelink|/properties(?:/[^/]+)?)?"),
        _issue_path,
    ),
    (re.compile(r"/rest/api/2/attachment/(?P<id>[1-9][0-9]*)"), _attachment_meta),
    (re.compile(r"/rest/dev-status/1\.0/issue/(?:summary|detail)"), _dev_status),
    (re.compile(r"/rest/gitplugin/1\.0/issues/branches"), _gij_branches),
    (re.compile(rf"/rest/gitplugin/1\.0/issues/{_REF}/commits"), _gij_commits),
    (re.compile(r"/rest/sla/1\.0/(?:search|slaSearch)"), _sla_search),
    (re.compile(r"/rest/tis/report/1\.0/api/issue"), _tis_issue),
    (re.compile(r"/rest/tis/report/1\.0/api/list2"), _tis_list),
    (re.compile(r"/rest/jeti/1\.0/email/(?:query|stat)"), _jeti),
]

_DOWNLOAD_RE = re.compile(r"/secure/(?:attachment|thumbnail)/(?P<id>[1-9][0-9]*)/[^/]+")


class GuardPolicy:
    """Request authorisation for :class:`~atlassian_admin_mcp.client.JiraClient`."""

    def __init__(self, search: Callable[[dict[str, str]], Awaitable[Any]]) -> None:
        self._search = search  # unguarded, uncached GET /rest/api/2/search

    async def authorize(self, path: str, params: dict[str, str]) -> dict[str, str]:
        """Return the (possibly rewritten) params, or raise :class:`GuardDenied`."""
        call = CURRENT.get()
        if path in ALWAYS_ALLOWED and not params:
            return params
        if call is None:
            raise GuardDenied(f"{path} is not allowed outside a guarded tool call")
        for pattern, rule in RULES:
            m = pattern.fullmatch(path)
            if m:
                return await rule(m, params, call, lambda refs: self._verify(call, refs))
        raise GuardDenied(f"{path} cannot be restricted by the guard and is not allowed")

    def authorize_sr(self) -> None:
        raise GuardDenied("the Groovy admin endpoint is not available while the guard is on")

    def authorize_download(self, path: str) -> None:
        call = CURRENT.get()
        m = _DOWNLOAD_RE.fullmatch(path)
        if call is None or m is None or m["id"] not in call.attachments:
            raise GuardDenied(f"download {path} is not released by a checked issue")

    def after_response(self, path: str, data: Any) -> None:
        """Release attachments of an issue that just passed the check."""
        call = CURRENT.get()
        if call is None or not RULES[0][0].fullmatch(path) or not isinstance(data, dict):
            return
        if "/" in path.removeprefix("/rest/api/2/issue/"):
            return  # sub-resources carry no attachment list
        fields = data.get("fields") or {}
        for att in fields.get("attachment") or []:
            if isinstance(att, dict) and att.get("id") is not None:
                call.attachments.add(str(att["id"]))

    async def _verify(self, call: CallGuard, raw_refs: list[str]) -> None:
        refs = [parse_issue_ref(r) for r in raw_refs]
        pending = sorted({r for r in refs if r not in call.verified})
        if not pending:
            return
        jql = f"({call.jql}) AND issuekey in ({', '.join(pending)})"
        try:
            data = await self._search(
                {
                    "jql": jql,
                    "fields": "key",
                    "maxResults": str(len(pending)),
                    "validateQuery": "strict",
                }
            )
        except Exception as exc:  # any failure while checking → deny
            raise GuardDenied(f"guard check failed: {exc}") from exc
        found_ids: set[str] = set()
        found_keys: set[str] = set()
        for issue in (data or {}).get("issues") or []:
            found_ids.add(str(issue.get("id", "")))
            found_keys.add(str(issue.get("key", "")).upper())
        for ref in pending:
            if ref not in (found_ids if is_numeric_id(ref) else found_keys):
                raise GuardDenied(f"issue {ref} is outside the guard or does not exist")
        call.verified.update(found_ids | found_keys)
