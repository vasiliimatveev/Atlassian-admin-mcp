"""Settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlsplit

from .jql import GuardDenied, validate_guard

DEFAULT_SR_PATH = "/rest/scriptrunner/latest/custom/atlassianAdmin"


class ConfigError(ValueError):
    """Raised when required settings are missing or invalid."""


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _int(env: dict[str, str], name: str, default: int, minimum: int = 0) -> int:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc
    if value < minimum:
        raise ConfigError(f"{name} must be >= {minimum}, got {value}")
    return value


def _float(env: dict[str, str], name: str, default: float) -> float:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc
    if value <= 0:
        raise ConfigError(f"{name} must be > 0, got {value}")
    return value


@dataclass(frozen=True)
class Settings:
    url: str
    personal_token: str | None = None
    username: str | None = None
    password: str | None = None
    ssl_verify: bool | str = True
    sr_path: str = DEFAULT_SR_PATH
    timeout: float = 60.0
    cache_ttl: int = 120
    max_concurrency: int = 8
    retries: int = 2
    json_indent: int | None = None
    max_response_chars: int = 100_000
    toolsets: str = ""
    guard_jql: str | None = None
    guard_header: str | None = None

    @property
    def guard_active(self) -> bool:
        return bool(self.guard_jql or self.guard_header)

    @property
    def origin(self) -> str:
        parts = urlsplit(self.url)
        return f"{parts.scheme}://{parts.netloc}"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        env = dict(os.environ if env is None else env)

        url = env.get("JIRA_URL", "").strip().rstrip("/")
        if not url:
            raise ConfigError("JIRA_URL is required (e.g. https://jira.example.com)")
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ConfigError(f"JIRA_URL must be an absolute http(s) URL, got {url!r}")

        token = env.get("JIRA_PERSONAL_TOKEN", "").strip() or None
        username = env.get("JIRA_USERNAME", "").strip() or None
        password = (
            env.get("JIRA_API_TOKEN", "").strip() or env.get("JIRA_PASSWORD", "").strip() or None
        )
        if not token and not (username and password):
            raise ConfigError(
                "Set JIRA_PERSONAL_TOKEN, or JIRA_USERNAME + JIRA_API_TOKEN/JIRA_PASSWORD"
            )

        raw_verify = env.get("JIRA_SSL_VERIFY", "").strip()
        ssl_verify: bool | str
        if raw_verify and raw_verify.lower() not in (
            "1",
            "0",
            "true",
            "false",
            "yes",
            "no",
            "on",
            "off",
        ):
            ssl_verify = raw_verify  # path to a CA bundle
        else:
            ssl_verify = _bool(raw_verify, True)

        sr_path = env.get("JIRA_ADMIN_SR_PATH", "").strip() or DEFAULT_SR_PATH
        if not sr_path.startswith("/"):
            sr_path = "/" + sr_path

        timeout = _float(env, "JIRA_ADMIN_TIMEOUT", _float(env, "JIRA_TIMEOUT", 60.0))
        indent = _int(env, "JIRA_ADMIN_JSON_INDENT", 0)

        guard_jql = env.get("JIRA_GUARD_JQL", "").strip() or None
        if guard_jql:
            try:
                validate_guard(guard_jql)
            except GuardDenied as exc:
                raise ConfigError(f"JIRA_GUARD_JQL: {exc}") from exc
        guard_header = env.get("JIRA_GUARD_HEADER", "").strip().lower() or None

        return cls(
            url=url,
            personal_token=token,
            username=username,
            password=password,
            ssl_verify=ssl_verify,
            sr_path=sr_path,
            timeout=timeout,
            cache_ttl=_int(env, "JIRA_ADMIN_CACHE_TTL", 120),
            max_concurrency=_int(env, "JIRA_ADMIN_MAX_CONCURRENCY", 8, minimum=1),
            retries=_int(env, "JIRA_ADMIN_RETRIES", 2),
            json_indent=indent or None,
            max_response_chars=_int(env, "JIRA_ADMIN_MAX_RESPONSE_CHARS", 100_000),
            toolsets=env.get("TOOLSETS", "").strip(),
            guard_jql=guard_jql,
            guard_header=guard_header,
        )
