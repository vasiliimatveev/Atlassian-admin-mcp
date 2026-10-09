"""Toolset ``dvcs`` — DVCS orgs/repos/sync audit, Git Integration (BigBrassBand), dev-status panel."""

import logging
from collections.abc import Callable
from typing import Annotated, Any

from fastmcp import Context
from pydantic import Field

from ..client import AnalystError
from ..util import error_json, get_client, seg, to_json

logger = logging.getLogger(__name__)


async def _resolve_issue_id(client: Any, issue: str) -> str:
    """Accept a numeric id or an issue key; dev-status only understands ids."""
    issue = issue.strip()
    if issue.isdigit():
        return issue
    data = await client.rest_get(f"/rest/api/2/issue/{seg(issue)}", fields="id")
    return str(data["id"])


def register(tool: Callable[..., Any]) -> None:  # noqa: C901 — flat list of thin wrappers
    # =====================================================================
    # DVCS + Git Integration inspection
    #
    # Three REST surfaces feed the "Git info panel" on a Jira issue:
    #
    #   1. Native Jira DVCS — ``/rest/bitbucket/1.0/`` (legacy name despite
    #      supporting GitHub/GitLab too). Owns the "DVCS accounts" admin
    #      page. Paginated singular noun (``organization``, not the plural
    #      form sometimes seen in community posts).
    #   2. BigBrassBand "Git Integration for Jira" — ``/rest/gitplugin/1.0/``
    #      (Marketplace app id 4984). NOT ``jgitplugin`` — that is a
    #      different, older, unrelated plugin.
    #   3. ``/rest/dev-status/1.0/`` — the API that actually renders the
    #      dev panel on the issue view, aggregating data from whichever
    #      provider plugin feeds it. Its ``applicationType`` is
    #      case-sensitive — ``stash`` for Bitbucket Server, ``GitHub``
    #      for github.com, ``githube`` for Enterprise, ``gitlab`` for
    #      GitLab via DVCS. The ``/summary`` endpoint returns the exact
    #      provider keys ("byInstanceType") that should then be passed
    #      to ``/detail``, so we drive the loop dynamically instead of
    #      hard-coding.
    # =====================================================================

    # ---- native DVCS ---------------------------------------------------

    @tool(
        tags={"read", "toolset:dvcs"},
        annotations={"title": "List DVCS Organizations", "readOnlyHint": True},
    )
    async def list_dvcs_organizations(
        ctx: Context,
        page: Annotated[int, Field(description="1-based page number.")] = 1,
        page_size: Annotated[int, Field(description="Page size (1..100).")] = 50,
    ) -> str:
        """List connected DVCS organizations (GitHub / GitLab / Bitbucket).

        Shows which Git providers are wired to Jira, their type and OAuth key.
        Paginated — pagination is not optional on DC. Backed by
        ``GET /rest/bitbucket/1.0/organization/page``.
        """
        client = get_client(ctx)
        try:
            return to_json(
                await client.rest_get(
                    "/rest/bitbucket/1.0/organization/page",
                    pagenum=max(1, int(page)),
                    pagesize=max(1, min(int(page_size), 100)),
                )
            )
        except AnalystError as exc:
            return error_json(f"list_dvcs_organizations failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:dvcs"},
        annotations={"title": "Get DVCS Organization", "readOnlyHint": True},
    )
    async def get_dvcs_organization(
        ctx: Context,
        organization_id: Annotated[str, Field(description="Organization id.")],
    ) -> str:
        """Get full configuration of one DVCS organization.

        Returns name, baseUrl, type, autolinkNewRepos, smartcommitsOnNewRepos,
        defaultGroupsSlugs, principal. Backed by
        ``GET /rest/bitbucket/1.0/organization/{id}``.
        """
        client = get_client(ctx)
        try:
            return to_json(
                await client.rest_get(f"/rest/bitbucket/1.0/organization/{seg(organization_id)}")
            )
        except AnalystError as exc:
            return error_json(f"get_dvcs_organization failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:dvcs"},
        annotations={"title": "List DVCS Repositories", "readOnlyHint": True},
    )
    async def list_dvcs_repositories(
        ctx: Context,
        organization_id: Annotated[str, Field(description="Organization id.")],
    ) -> str:
        """List repositories synced from a DVCS organization.

        Per-repo: slug, linked, smartcommitsEnabled, lastCommitDate,
        activityLastUpdatedTimestamp. Backed by
        ``GET /rest/bitbucket/1.0/organization/{id}/repository`` (note the
        documented singular ``/repository``).
        """
        client = get_client(ctx)
        try:
            return to_json(
                await client.rest_get(
                    f"/rest/bitbucket/1.0/organization/{seg(organization_id)}/repository"
                )
            )
        except AnalystError as exc:
            return error_json(f"list_dvcs_repositories failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:dvcs"},
        annotations={"title": "Get DVCS Repository", "readOnlyHint": True},
    )
    async def get_dvcs_repository(
        ctx: Context,
        repository_id: Annotated[str, Field(description="Repository id.")],
    ) -> str:
        """Get one DVCS-linked repository by id — slug, sync settings, activity timestamps.

        Backed by ``GET /rest/bitbucket/1.0/repository/{id}``.
        """
        client = get_client(ctx)
        try:
            return to_json(
                await client.rest_get(f"/rest/bitbucket/1.0/repository/{seg(repository_id)}")
            )
        except AnalystError as exc:
            return error_json(f"get_dvcs_repository failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:dvcs"},
        annotations={"title": "DVCS Sync Audit", "readOnlyHint": True},
    )
    async def get_dvcs_sync_audit(
        ctx: Context,
        repository_id: Annotated[
            str,
            Field(
                description=(
                    "Repository id to audit. Omit to read the instance-wide "
                    "audit log via ``/audit/repository/all``."
                )
            ),
        ] = "",
    ) -> str:
        """Diagnose why the Git dev panel isn't updating — DVCS sync audit log.

        The canonical "last sync time + error message" endpoint: firstRequestDate,
        lastActivityDate, totalChangesetCount, flightTimeMs and — on failure —
        exception + message + status (``OK`` / ``SYNC_ERROR`` / ``SYNC_WARNING``).
        Backed by ``GET /rest/bitbucket/1.0/audit/repository/{id|all}``.

        A common mistake is to hit ``/repository/{id}/sync`` for status —
        that path is the resync trigger, not a status read.
        """
        client = get_client(ctx)
        path = (
            f"/rest/bitbucket/1.0/audit/repository/{seg(repository_id)}"
            if repository_id
            else "/rest/bitbucket/1.0/audit/repository/all"
        )
        try:
            return to_json(await client.rest_get(path, cache=False))
        except AnalystError as exc:
            return error_json(f"get_dvcs_sync_audit failed: {exc}", status=exc.status)

    # ---- BigBrassBand Git Integration for Jira (GIJ) ----------------

    @tool(
        tags={"read", "toolset:dvcs"},
        annotations={"title": "GIJ: Issue Commits", "readOnlyHint": True},
    )
    async def list_gij_issue_commits(
        ctx: Context,
        issue_key: Annotated[str, Field(description="Issue key, e.g. 'HR-123'.")],
        show_files: Annotated[
            bool,
            Field(description="If true, each commit also lists changed files with change type."),
        ] = False,
    ) -> str:
        """List Git commits linked to a Jira issue via the BigBrassBand plugin.

        Useful for "which commits reference this ticket" — richer than
        dev-status (full SHAs, author emails, messages). Respects issue-view
        permission. Backed by ``GET /rest/gitplugin/1.0/issues/{key}/commits``.
        """
        client = get_client(ctx)
        try:
            return to_json(
                await client.rest_get(
                    f"/rest/gitplugin/1.0/issues/{seg(issue_key)}/commits",
                    showfiles="true" if show_files else "false",
                )
            )
        except AnalystError as exc:
            return error_json(f"list_gij_issue_commits failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:dvcs"},
        annotations={"title": "GIJ: Issue Branches", "readOnlyHint": True},
    )
    async def list_gij_issue_branches(
        ctx: Context,
        issue_key: Annotated[
            str,
            Field(
                description=(
                    "Issue key. Omit to list ALL indexed branches across the "
                    "instance — large response, prefer a specific issue."
                )
            ),
        ] = "",
    ) -> str:
        """List Git branches linked to a Jira issue via the BigBrassBand plugin.

        Useful when the dev panel misses a feature branch developers are
        working on. Backed by
        ``GET /rest/gitplugin/1.0/issues/branches?key=<issueKey>``.
        """
        client = get_client(ctx)
        try:
            params: dict[str, Any] = {}
            if issue_key:
                params["key"] = issue_key
            return to_json(await client.rest_get("/rest/gitplugin/1.0/issues/branches", **params))
        except AnalystError as exc:
            return error_json(f"list_gij_issue_branches failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:dvcs"},
        annotations={"title": "GIJ: Commit Reverse Lookup", "readOnlyHint": True},
    )
    async def get_gij_commit_issues(
        ctx: Context,
        commit_sha: Annotated[
            str,
            Field(description="Full or shortened commit SHA as indexed by GIJ."),
        ],
    ) -> str:
        """Find which Jira issues a commit is linked to — reverse commit→issue lookup.

        Answers "why is this commit showing up on ticket X" or "is this commit
        linked anywhere". Backed by
        ``GET /rest/gitplugin/1.0/commit/{sha}/issues``.
        """
        client = get_client(ctx)
        try:
            return to_json(
                await client.rest_get(f"/rest/gitplugin/1.0/commit/{seg(commit_sha)}/issues")
            )
        except AnalystError as exc:
            return error_json(f"get_gij_commit_issues failed: {exc}", status=exc.status)

    # ---- dev-status (raw panel data) --------------------------------

    @tool(
        tags={"read", "toolset:dvcs"},
        annotations={"title": "Dev Panel Summary", "readOnlyHint": True},
    )
    async def get_issue_dev_summary(
        ctx: Context,
        issue_id: Annotated[
            str,
            Field(
                description=(
                    "Numeric issue id, or an issue key such as 'HR-123' "
                    "(resolved to the id automatically)."
                )
            ),
        ],
    ) -> str:
        """Summary of the Git dev panel on an issue — counts of PRs/MRs, branches, commits, repositories.

        Use this FIRST for any Git-panel question. The response also
        contains ``byInstanceType`` keys that are the valid
        ``applicationType`` strings for ``get_issue_dev_detail`` — drive
        the follow-up loop from those keys instead of hard-coding provider
        names. Backed by ``GET /rest/dev-status/1.0/issue/summary?issueId=<id>``.
        """
        client = get_client(ctx)
        try:
            issue_id = await _resolve_issue_id(client, issue_id)
            return to_json(
                await client.rest_get("/rest/dev-status/1.0/issue/summary", issueId=issue_id)
            )
        except AnalystError as exc:
            return error_json(f"get_issue_dev_summary failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:dvcs"},
        annotations={"title": "Dev Panel Detail", "readOnlyHint": True},
    )
    async def get_issue_dev_detail(
        ctx: Context,
        issue_id: Annotated[str, Field(description="Numeric issue id or issue key.")],
        application_type: Annotated[
            str,
            Field(
                description=(
                    "Case-sensitive provider key from ``get_issue_dev_summary`` "
                    "(``stash`` for Bitbucket Server/DC, ``GitHub``, ``githube`` "
                    "for GitHub Enterprise, ``gitlab`` via DVCS, ``bitbucket`` "
                    "for Bitbucket Cloud)."
                )
            ),
        ],
        data_type: Annotated[
            str,
            Field(
                description=(
                    "One of ``repository`` (commits nested under repos), "
                    "``branch`` (branches + linked PRs), or ``pullrequest`` "
                    "(PRs at top level). Singular — not ``pullrequests``."
                )
            ),
        ],
    ) -> str:
        """Get the full Git dev-panel detail for an issue — raw commits / branches / PRs.

        The UI-equivalent payload the issue view renders. Structure:
        ``{detail:[{_instance, repositories[{commits[]}], branches[],
        pullRequests[]}]}``. Backed by ``GET /rest/dev-status/1.0/issue/detail``.
        """
        if data_type not in ("repository", "branch", "pullrequest"):
            return error_json(
                "data_type must be 'repository', 'branch', or 'pullrequest' (singular)"
            )
        if not application_type:
            return error_json("application_type is required (case-sensitive provider key)")
        client = get_client(ctx)
        try:
            issue_id = await _resolve_issue_id(client, issue_id)
            return to_json(
                await client.rest_get(
                    "/rest/dev-status/1.0/issue/detail",
                    issueId=issue_id,
                    applicationType=application_type,
                    dataType=data_type,
                )
            )
        except AnalystError as exc:
            return error_json(f"get_issue_dev_detail failed: {exc}", status=exc.status)
