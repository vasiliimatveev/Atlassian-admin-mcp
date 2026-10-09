"""Small helpers shared by tool modules."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

if TYPE_CHECKING:
    from fastmcp import Context

    from .client import AnalystClient

_json_indent: int | None = None


class InvalidArgument(ValueError):
    """A tool argument that cannot be sent to Jira as-is."""


def set_json_indent(indent: int | None) -> None:
    global _json_indent
    _json_indent = indent


def to_json(data: Any) -> str:
    """Serialise a tool result. Compact by default — it is read by an LLM."""
    if _json_indent:
        return json.dumps(data, ensure_ascii=False, indent=_json_indent)
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def error_json(msg: str, **extra: Any) -> str:
    payload: dict[str, Any] = {"error": msg}
    payload.update({k: v for k, v in extra.items() if v is not None})
    return to_json(payload)


def seg(value: Any) -> str:
    """Encode one URL path segment.

    Every caller-supplied value interpolated into a REST path goes through
    here, so ``issue_key="../../plugins/1.0/"`` cannot escape the intended
    endpoint.
    """
    text = str(value).strip()
    if text in ("", ".", ".."):
        raise InvalidArgument(f"invalid path segment: {value!r}")
    return quote(text, safe="")


def get_client(ctx: Context) -> AnalystClient:
    return ctx.lifespan_context["client"]
