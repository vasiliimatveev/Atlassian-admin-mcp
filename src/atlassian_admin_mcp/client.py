"""Async HTTP client for Jira Data Center.

* one pooled ``httpx.AsyncClient`` per server (keep-alive, no per-call TLS setup);
* a concurrency cap so a burst of parallel tool calls cannot flood Jira;
* a short TTL cache plus in-flight de-duplication for GETs — admin
  configuration changes rarely, and agents tend to re-read the same objects;
* retries with backoff on 429/502/503/504 and transport errors;
* credentials never leave the configured origin, and downloads are capped
  while streaming.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import OrderedDict
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from .config import Settings
from .guard import SEARCH_PATH, GuardPolicy
from .util import InvalidArgument

logger = logging.getLogger(__name__)

RETRY_STATUSES = frozenset({429, 502, 503, 504})
_MAX_BACKOFF = 10.0
_BODY_PREVIEW = 500


class JiraError(Exception):
    """A failed call to Jira or the Groovy admin endpoint."""

    def __init__(
        self,
        message: str,
        status: int | None = None,
        body: str | None = None,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.body = body
        self.url = url


class _TTLCache:
    """Small LRU cache of raw response bodies with a per-entry TTL."""

    def __init__(self, ttl: float, maxsize: int = 512) -> None:
        self.ttl = ttl
        self.maxsize = maxsize
        self._data: OrderedDict[Any, tuple[float, bytes]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: Any) -> bytes | None:
        item = self._data.get(key)
        if item is None:
            self.misses += 1
            return None
        expires, body = item
        if expires < time.monotonic():
            del self._data[key]
            self.misses += 1
            return None
        self._data.move_to_end(key)
        self.hits += 1
        return body

    def put(self, key: Any, body: bytes) -> None:
        self._data[key] = (time.monotonic() + self.ttl, body)
        self._data.move_to_end(key)
        while len(self._data) > self.maxsize:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)


_DOT_SEGMENTS = frozenset({".", "..", "%2e", "%2e%2e", ".%2e", "%2e."})
# Characters servlet containers treat specially inside a path: ';' starts path
# parameters (Tomcat strips them when routing), '\\' and encoded '/' or '\\' are
# normalised differently by proxies and Tomcat. None occur in real Jira ids.
_UNSAFE_IN_PATH = (";", "\\", "%2f", "%5c", "%3b", "%00")


def _check_segments(path: str) -> None:
    lowered = path.lower()
    if any(part in _DOT_SEGMENTS for part in lowered.split("/")):
        raise InvalidArgument(f"dot segments are not allowed in paths: {path!r}")
    bad = [c for c in _UNSAFE_IN_PATH if c in lowered]
    if bad:
        raise InvalidArgument(f"path contains {bad} — not a valid Jira id or key: {path!r}")


def _check_path(path: str) -> None:
    if not path.startswith("/"):
        raise InvalidArgument(f"REST path must start with '/': {path!r}")
    _check_segments(urlsplit(path).path)


def _clean(params: dict[str, Any]) -> dict[str, str]:
    return {k: str(v) for k, v in params.items() if v is not None and v != ""}


def _parse_json(body: bytes, where: str, status: int, url: str) -> Any:
    if not body.strip():
        return {}
    try:
        return json.loads(body)
    except ValueError as exc:
        preview = body[:_BODY_PREVIEW].decode("utf-8", errors="replace")
        hint = ""
        if preview.lstrip().lower().startswith(("<!doctype", "<html")):
            hint = " (got HTML — usually a login/SSO page or a wrong path)"
        raise JiraError(
            f"{where} returned non-JSON{hint}", status=status, body=preview, url=url
        ) from exc


class JiraClient:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self._base_url = settings.url.rstrip("/")
        base = urlsplit(self._base_url)
        self._scheme, self._netloc = base.scheme, base.netloc
        self._base_path = base.path.rstrip("/")

        headers = {"User-Agent": "atlassian-admin-mcp"}
        auth: httpx.Auth | None = None
        if settings.personal_token:
            headers["Authorization"] = f"Bearer {settings.personal_token}"
        elif settings.username and settings.password:
            auth = httpx.BasicAuth(settings.username, settings.password)

        self._http = httpx.AsyncClient(
            headers=headers,
            auth=auth,
            verify=settings.ssl_verify,
            timeout=httpx.Timeout(settings.timeout, connect=min(settings.timeout, 15.0)),
            limits=httpx.Limits(
                max_connections=settings.max_concurrency * 2,
                max_keepalive_connections=settings.max_concurrency,
            ),
            follow_redirects=False,
            transport=transport,
        )
        self._sem = asyncio.Semaphore(settings.max_concurrency)
        self._cache = _TTLCache(settings.cache_ttl) if settings.cache_ttl > 0 else None
        self._inflight: dict[Any, asyncio.Future[bytes]] = {}
        self.guard = GuardPolicy(self._search_unguarded) if settings.guard_active else None

    async def aclose(self) -> None:
        await self._http.aclose()

    @property
    def sr_url(self) -> str:
        return f"{self._base_url}{self.settings.sr_path}"

    def cache_stats(self) -> dict[str, Any]:
        if self._cache is None:
            return {"enabled": False}
        return {
            "enabled": True,
            "ttlSeconds": self._cache.ttl,
            "entries": len(self._cache),
            "hits": self._cache.hits,
            "misses": self._cache.misses,
        }

    def clear_cache(self) -> None:
        if self._cache is not None:
            self._cache.clear()

    # ------------------------------------------------------------------ JSON

    async def sr_action(self, action: str, *, cache: bool = True, **params: Any) -> Any:
        """Call the Groovy endpoint: ``GET <sr_path>?action=<action>&...``."""
        if self.guard is not None:
            self.guard.authorize_sr()
        query = {"action": action, **params}
        return await self._get_json(
            self.sr_url, query, "application/json", cache, f"SR action={action}"
        )

    async def rest_get(
        self,
        path: str,
        *,
        accept: str = "application/json",
        cache: bool = True,
        **params: Any,
    ) -> Any:
        """GET a REST path relative to ``JIRA_URL``.

        ``accept`` matters for UPM (vendor media type, otherwise HTML) and
        applinks (XML unless JSON is requested).
        """
        _check_path(path)
        query = _clean(params)
        url = f"{self._base_url}{path}"
        if self.guard is None:
            return await self._get_json(url, query, accept, cache, f"GET {path}")
        query = await self.guard.authorize(path, query)
        data = await self._get_json(url, query, accept, cache, f"GET {path}")
        self.guard.after_response(path, data)
        return data

    async def _search_unguarded(self, params: dict[str, str]) -> Any:
        """Issue search used by the guard itself — never cached, never guarded."""
        return await self._get_json(
            f"{self._base_url}{SEARCH_PATH}", params, "application/json", False, "guard check"
        )

    async def _get_json(
        self, url: str, params: dict[str, Any], accept: str, cache: bool, where: str
    ) -> Any:
        query = _clean(params)
        if not cache or self._cache is None:
            return _parse_json(await self._fetch(url, query, accept, where), where, 200, url)

        key = (url, tuple(sorted(query.items())), accept)
        body = self._cache.get(key)
        if body is None:
            body = await self._join_inflight(key)
        if body is None:
            body = await self._fetch_shared(key, url, query, accept, where)
        return _parse_json(body, where, 200, url)

    async def _join_inflight(self, key: Any) -> bytes | None:
        """Wait for an identical request that is already running, if any."""
        pending = self._inflight.get(key)
        if pending is None:
            return None
        try:
            return await asyncio.shield(pending)
        except asyncio.CancelledError:
            if not pending.cancelled():
                raise
            return None  # the request we piggy-backed on was cancelled — fetch ourselves

    async def _fetch_shared(
        self, key: Any, url: str, query: dict[str, str], accept: str, where: str
    ) -> bytes:
        """Fetch once, let concurrent identical callers share the result, then cache it."""
        assert self._cache is not None
        future: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()
        self._inflight[key] = future
        try:
            body = await self._fetch(url, query, accept, where)
        except asyncio.CancelledError:
            future.cancel()
            raise
        except Exception as exc:
            future.set_exception(exc)
            future.exception()  # mark retrieved: there may be no waiters
            raise
        finally:
            self._inflight.pop(key, None)
        future.set_result(body)
        self._cache.put(key, body)
        return body

    async def _fetch(self, url: str, query: dict[str, str], accept: str, where: str) -> bytes:
        attempts = self.settings.retries + 1
        for attempt in range(attempts):
            last = attempt == attempts - 1
            try:
                async with self._sem:
                    resp = await self._http.get(url, params=query, headers={"Accept": accept})
            except httpx.TransportError as exc:
                if last:
                    raise JiraError(f"{where}: transport error: {exc!r}", url=url) from exc
                await asyncio.sleep(self._backoff(attempt, None))
                continue

            if resp.status_code in RETRY_STATUSES and not last:
                await asyncio.sleep(self._backoff(attempt, resp.headers.get("Retry-After")))
                continue
            if not resp.is_success:
                preview = resp.text[:_BODY_PREVIEW] if resp.content else ""
                logger.warning("HTTP %s from %s: %s", resp.status_code, where, preview)
                raise JiraError(
                    f"{where} returned HTTP {resp.status_code}",
                    status=resp.status_code,
                    body=preview,
                    url=url,
                )
            return resp.content
        raise AssertionError("unreachable")

    @staticmethod
    def _backoff(attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(float(retry_after), _MAX_BACKOFF)
            except ValueError:
                pass
        return min(0.5 * 2**attempt, _MAX_BACKOFF)

    # ----------------------------------------------------------------- bytes

    def _same_origin(self, url: str) -> str:
        """Pin a (possibly absolute) URL from Jira to the configured origin.

        Attachment metadata carries URLs built from Jira's *base URL*, which
        may differ from ``JIRA_URL`` (proxy vs internal host) — or be
        attacker-controlled. Only the path and query are kept, so the
        session credentials are never sent anywhere else.
        """
        if not url:
            raise InvalidArgument("empty download URL")
        parts = urlsplit(url)
        if parts.scheme and parts.scheme not in ("http", "https"):
            raise InvalidArgument(f"unsupported URL scheme in {url!r}")
        # Check before any joining: urljoin would silently collapse "..".
        _check_segments(parts.path)
        if parts.scheme or parts.netloc:
            # Absolute URL from Jira: its path already includes the context path.
            path = parts.path or "/"
            if (parts.scheme, parts.netloc) != (self._scheme, self._netloc):
                logger.info("re-rooting %s onto configured JIRA_URL origin", url)
        else:
            path = f"{self._base_path}/{parts.path.lstrip('/')}"
        return urlunsplit((self._scheme, self._netloc, path, parts.query, ""))

    async def fetch_bytes(self, url: str, *, max_bytes: int | None = None) -> bytes:
        """Download raw bytes (attachments, thumbnails) with a hard size cap."""
        target = self._same_origin(url)
        if self.guard is not None:
            path = urlsplit(target).path
            self.guard.authorize_download(path.removeprefix(self._base_path) or "/")
        where = f"GET {urlsplit(target).path}"
        try:
            async with self._sem, self._http.stream("GET", target) as resp:
                if not resp.is_success:
                    await resp.aread()
                    raise JiraError(
                        f"{where} returned HTTP {resp.status_code}",
                        status=resp.status_code,
                        body=resp.text[:_BODY_PREVIEW],
                        url=target,
                    )
                declared = resp.headers.get("Content-Length")
                if (
                    max_bytes is not None
                    and declared
                    and declared.isdigit()
                    and int(declared) > max_bytes
                ):
                    raise JiraError(
                        f"content-length {declared} exceeds limit {max_bytes}", status=413
                    )
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if max_bytes is not None and total > max_bytes:
                        raise JiraError(f"download exceeds limit {max_bytes} bytes", status=413)
                    chunks.append(chunk)
                return b"".join(chunks)
        except httpx.TransportError as exc:
            raise JiraError(f"{where}: transport error: {exc!r}", url=target) from exc
