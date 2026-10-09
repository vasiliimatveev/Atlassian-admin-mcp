"""Toolset catalogue and ``TOOLSETS`` parsing."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Toolset:
    name: str
    description: str
    requires: str
    default: bool = False


TOOLSETS: dict[str, Toolset] = {
    t.name: t
    for t in (
        Toolset(
            "admin",
            "Workflows (+ raw XML, transition conditions/validators/post-functions), "
            "screens, permission/notification/workflow/field-config/issue-security "
            "schemes, groups, roles, licensing, cluster, reindex",
            "Groovy endpoint",
            default=True,
        ),
        Toolset(
            "scriptrunner",
            "Listeners, behaviours, scripted fields, fragments, "
            "jobs, REST endpoints, escalation services — with full Groovy source",
            "ScriptRunner + Groovy endpoint",
        ),
        Toolset("jmwe", "JMWE event-based and shared actions", "JMWE + Groovy endpoint"),
        Toolset(
            "structure", "ALM Works Structure + Structure.Gantt", "Structure + Groovy endpoint"
        ),
        Toolset(
            "assets",
            "Insight / Assets CMDB: schemas, object types, AQL, imports",
            "Assets + Groovy endpoint",
        ),
        Toolset("automation", "Automation for Jira rules", "Automation for Jira"),
        Toolset("logs", "Audit log and atlassian-jira.log tail", "Jira admin", default=True),
        Toolset(
            "integrations",
            "UPM plugins and modules, webhooks, application links, dark features",
            "Jira admin",
            default=True,
        ),
        Toolset(
            "issue_inspect",
            "Attachment content (vision + text), thumbnails, votes, remote links",
            "Browse permission",
            default=True,
        ),
        Toolset(
            "dvcs",
            "DVCS orgs/repos/sync audit, Git Integration (BigBrassBand), dev-status panel",
            "DVCS connector / Git Integration",
        ),
        Toolset(
            "properties",
            "Entity properties on projects, issues and users",
            "Browse permission",
            default=True,
        ),
        Toolset("sla", "Time to SLA (Appfire/SaaSJet)", "Time to SLA"),
        Toolset("time_in_status", "Timepiece — Time in Status (OBSS)", "Timepiece"),
        Toolset("email", "Email This Issue (JETI) audit log and mail queues", "JETI"),
    )
}

_LEGACY_PREFIX = "jira_analyst_"


def resolve_toolsets(spec: str) -> set[str]:
    """Turn a ``TOOLSETS`` value into a set of toolset names.

    ``""`` / ``default`` → the default set; ``all`` → everything. Names may
    carry the legacy ``jira_analyst_`` prefix. Unknown names are logged and
    ignored; if nothing valid remains the result is empty (fail closed).
    """
    names = [n.strip().lower() for n in spec.split(",") if n.strip()]
    if not names:
        names = ["default"]
    enabled: set[str] = set()
    unknown: list[str] = []
    for name in names:
        name = name.removeprefix(_LEGACY_PREFIX)
        if name == "all":
            enabled.update(TOOLSETS)
        elif name == "default":
            enabled.update(n for n, t in TOOLSETS.items() if t.default)
        elif name in TOOLSETS:
            enabled.add(name)
        else:
            unknown.append(name)
    if unknown:
        logger.warning(
            "Unknown toolsets ignored: %s (valid: %s, default, all)",
            ", ".join(unknown),
            ", ".join(TOOLSETS),
        )
    return enabled
