from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from fastmcp import Client

from jira_dc_analyst.client import AnalystClient
from jira_dc_analyst.config import DEFAULT_SR_PATH, Settings
from jira_dc_analyst.server import create_server

BASE = "https://jira.example.com"

Responder = Callable[[httpx.Request], httpx.Response]


class FakeJira:
    """In-process stand-in for Jira: route by path (and by ``action`` for the Groovy endpoint)."""

    def __init__(self, base: str = BASE) -> None:
        self.base = base
        self.routes: dict[str, Responder] = {}
        self.sr_routes: dict[str, Responder] = {}
        self.requests: list[httpx.Request] = []
        self.fallback: Responder | None = None

    @staticmethod
    def _responder(
        payload: Any = None,
        status: int = 200,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> Responder:
        def respond(_req: httpx.Request) -> httpx.Response:
            if content is not None:
                return httpx.Response(status, content=content, headers=headers)
            return httpx.Response(status, json=payload, headers=headers)

        return respond

    def add(self, path: str, payload: Any = None, status: int = 200, **kw: Any) -> None:
        self.routes[path] = self._responder(payload, status, **kw)

    def add_handler(self, path: str, handler: Responder) -> None:
        self.routes[path] = handler

    def sr(self, action: str, payload: Any = None, status: int = 200) -> None:
        self.sr_routes[action] = self._responder(payload, status)

    def paths(self) -> list[str]:
        return [r.url.raw_path.decode().split("?")[0] for r in self.requests]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path.endswith(DEFAULT_SR_PATH):
            action = request.url.params.get("action", "")
            if action in self.sr_routes:
                return self.sr_routes[action](request)
        raw = request.url.raw_path.decode().split("?")[0]
        for key in (raw, path):
            if key in self.routes:
                return self.routes[key](request)
        if self.fallback is not None:
            return self.fallback(request)
        return httpx.Response(404, json={"errorMessages": [f"no route {raw}"]})


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "url": BASE,
        "personal_token": "test-token",
        "toolsets": "all",
        "retries": 0,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def jira() -> FakeJira:
    return FakeJira()


@pytest.fixture
def client_factory(jira: FakeJira):
    clients: list[AnalystClient] = []

    def make(**overrides: Any) -> AnalystClient:
        c = AnalystClient(make_settings(**overrides), transport=httpx.MockTransport(jira))
        clients.append(c)
        return c

    yield make


@pytest.fixture
def mcp_client(jira: FakeJira):
    """``async with mcp_client(**settings) as c`` → fastmcp Client wired to FakeJira."""

    def make(**overrides: Any) -> Client:
        server = create_server(make_settings(**overrides), transport=httpx.MockTransport(jira))
        return Client(server)

    return make


def payload(result: Any) -> Any:
    """Parse the JSON text of a tool result (first content block)."""
    return json.loads(result.content[0].text)
