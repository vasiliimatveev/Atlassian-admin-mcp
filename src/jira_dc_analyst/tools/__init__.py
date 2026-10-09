"""Tool modules, one per toolset. Each exposes ``register(tool)``."""

from . import (
    admin,
    assets,
    automation,
    dvcs,
    email,
    integrations,
    issue_inspect,
    jmwe,
    logs,
    properties,
    scriptrunner,
    sla,
    structure,
    time_in_status,
)

MODULES = (
    admin,
    scriptrunner,
    jmwe,
    structure,
    assets,
    automation,
    logs,
    integrations,
    issue_inspect,
    dvcs,
    properties,
    sla,
    time_in_status,
    email,
)
