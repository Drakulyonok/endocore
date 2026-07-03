"""Shared test helpers for the EndoCore framework test suite."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from endocore.core.application import Application

EXAMPLE_DIR = Path(__file__).resolve().parent.parent / "example"


@pytest.fixture(scope="session")
def app() -> Application:
    """A booted Application rooted at the bundled example app."""
    return Application(app_dir=EXAMPLE_DIR)


def call(app: Application, method: str, path: str, *, body: bytes = b"",
         headers: list[tuple[bytes, bytes]] | None = None,
         query: bytes = b"") -> tuple[int, bytes, dict[str, str]]:
    """Drive one HTTP request through the ASGI app; return (status, body, headers)."""

    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": query,
        "headers": headers or [],
    }
    sent: list[dict] = []

    async def receive() -> dict:
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: dict) -> None:
        sent.append(message)

    asyncio.run(app(scope, receive, send))

    start = next(m for m in sent if m["type"] == "http.response.start")
    body_msg = next(m for m in sent if m["type"] == "http.response.body")
    # HTTP header names are case-insensitive; normalize to lower-case for lookups.
    resp_headers = {k.decode().lower(): v.decode() for k, v in start["headers"]}
    return start["status"], body_msg["body"], resp_headers
