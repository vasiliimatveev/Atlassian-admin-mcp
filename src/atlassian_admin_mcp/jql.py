"""JQL helpers for the guard: balance checks, splicing, issue-reference parsing.

Deliberately conservative: anything that cannot be parsed with certainty is
rejected rather than passed through.
"""

from __future__ import annotations

import re
from urllib.parse import unquote


class GuardDenied(Exception):
    """The guard refused a call. Never caught by tools — always surfaces as an error."""


_KEY_RE = re.compile(r"[A-Z][A-Z0-9_]*-[1-9][0-9]*")
_ID_RE = re.compile(r"[1-9][0-9]{0,18}")
_ORDER_BY_RE = re.compile(r"order\s+by\b", re.IGNORECASE)
_SORT_FIELD = r'(?:[A-Za-z_][A-Za-z0-9_.]*|cf\[[0-9]+\]|"[^"\\]+")(?:\s+(?:asc|desc))?'
_ORDER_CLAUSE_RE = re.compile(
    rf"order\s+by\s+{_SORT_FIELD}(?:\s*,\s*{_SORT_FIELD})*", re.IGNORECASE
)


def _scan(jql: str) -> list[tuple[int, str]]:
    """Return ``(position, char)`` for every char outside string literals.

    Raises :class:`GuardDenied` on unterminated strings, a dangling escape or
    unbalanced parentheses — the classic ``x) OR (y`` break-out.
    """
    depth = 0
    quote: str | None = None
    escaped = False
    outside: list[tuple[int, str]] = []
    for i, ch in enumerate(jql):
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch in ('"', "'"):
            quote = ch
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                raise GuardDenied("JQL has an unbalanced ')'")
        outside.append((i, ch if depth == 0 else "\0"))
    if quote or escaped:
        raise GuardDenied("JQL has an unterminated string literal")
    if depth:
        raise GuardDenied("JQL has an unbalanced '('")
    return outside


def split_order_by(jql: str) -> tuple[str, str]:
    """Split ``jql`` into ``(where, order_by)`` at a top-level ``ORDER BY``."""
    visible = ["\0"] * len(jql)
    for i, ch in _scan(jql):
        visible[i] = ch
    flat = "".join(visible)  # string literals and nested groups masked out
    matches = [
        m
        for m in _ORDER_BY_RE.finditer(flat)
        if m.start() == 0 or not (flat[m.start() - 1].isalnum() or flat[m.start() - 1] == "_")
    ]
    if not matches:
        return jql.strip(), ""
    if len(matches) > 1:
        raise GuardDenied("JQL has more than one ORDER BY")
    pos = matches[0].start()
    order = jql[pos:].strip()
    # Only a plain sort list may follow — no way to smuggle a condition past the guard.
    if not _ORDER_CLAUSE_RE.fullmatch(order):
        raise GuardDenied(f"unsupported ORDER BY clause: {order!r}")
    return jql[:pos].strip(), order


def validate_guard(guard: str) -> str:
    guard = guard.strip()
    if not guard:
        raise GuardDenied("guard JQL is empty")
    where, order = split_order_by(guard)
    if order:
        raise GuardDenied("guard JQL must not contain ORDER BY")
    if not where:
        raise GuardDenied("guard JQL is empty")
    return where


def combine(guard: str, jql: str) -> str:
    """``(<guard>) AND (<jql>) [ORDER BY …]`` — the only way user JQL reaches Jira."""
    guard = validate_guard(guard)
    where, order = split_order_by(jql or "")
    combined = f"({guard})" if not where else f"({guard}) AND ({where})"
    return f"{combined} {order}" if order else combined


def parse_issue_ref(value: object) -> str:
    """Normalise an issue key or numeric id, or refuse.

    Jira DC resolves keys case-insensitively and URL-decodes paths, so
    ``sos-1`` and ``SOS%2D1`` both mean ``SOS-1``. Decode once, upper-case,
    then demand an exact key/id shape — anything else (double encoding,
    spaces, separators, JQL fragments) is denied.
    """
    text = unquote(str(value)).strip().upper()
    if "%" in text:
        raise GuardDenied(f"issue reference {value!r} is encoded more than once")
    if _KEY_RE.fullmatch(text) or _ID_RE.fullmatch(text):
        return text
    raise GuardDenied(f"not an issue key or id: {value!r}")


def is_numeric_id(ref: str) -> bool:
    return ref.isdigit()
