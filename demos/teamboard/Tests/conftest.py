"""Shared test harness: a booted app on a fresh in-memory DB per test."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_app = None


def _application():
    global _app
    if _app is None:
        from endocore.core.application import Application

        _app = Application(app_dir=ROOT)
    return _app


@pytest.fixture()
def app():
    from endocore.orm import configure, create_all
    from endocore.orm.connection import get_connection

    from Models.core import ALL_MODELS

    application = _application()
    configure(backend="sqlite", database=":memory:")
    create_all(*ALL_MODELS)
    yield application
    get_connection().close()


async def acall(app, method: str, path: str, *, body: dict | None = None,
                cookie: str | None = None):
    """Drive one HTTP request; returns (status, parsed_json, headers)."""
    headers = [(b"content-type", b"application/json")]
    if cookie:
        headers.append((b"cookie", f"session={cookie}".encode()))
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": b"",
        "headers": headers,
    }
    raw = json.dumps(body).encode() if body is not None else b""
    sent: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": raw, "more_body": False}

    async def send(message):
        sent.append(message)

    await app(scope, receive, send)
    start = next(m for m in sent if m["type"] == "http.response.start")
    payload = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    resp_headers = {k.decode().lower(): v.decode() for k, v in start["headers"]}
    return start["status"], json.loads(payload) if payload else None, resp_headers


def session_of(headers: dict[str, str]) -> str:
    match = re.match(r"session=([^;]*)", headers.get("set-cookie", ""))
    assert match, f"no session cookie in {headers!r}"
    return match.group(1)


async def register(app, email: str, name: str = "User") -> str:
    """Create an account; returns its session cookie."""
    status, _, headers = await acall(
        app, "POST", "/v1/auth/register",
        body={"email": email, "name": name, "password": "password123"},
    )
    assert status == 201, status
    return session_of(headers)
