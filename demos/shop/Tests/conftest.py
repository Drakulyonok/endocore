"""Shared test harness.

By default the suite runs on in-memory SQLite. Set
``ENDOCORE_TEST_POSTGRES_DSN`` to run the *same* suite — including the money
races — against a real PostgreSQL with ``pool_size=5``, which is the
configuration that must be proven before production.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DSN = os.environ.get("ENDOCORE_TEST_POSTGRES_DSN")

_app = None


def _application():
    global _app
    if _app is None:
        from endocore.core.application import Application

        _app = Application(app_dir=ROOT)
    return _app


def _drop_all(conn, models) -> None:
    cascade = " CASCADE" if conn.backend.name == "postgres" else ""
    for model in reversed(models):
        conn.executescript(f'DROP TABLE IF EXISTS "{model._meta.table}"{cascade}')


@pytest.fixture()
def app():
    from endocore.orm import configure, create_all

    from Models.core import ALL_MODELS

    application = _application()
    if DSN:
        conn = configure(backend="postgres", conninfo=DSN, pool_size=5)
        _drop_all(conn, ALL_MODELS)
    else:
        conn = configure(backend="sqlite", database=":memory:")
    create_all(*ALL_MODELS)
    yield application
    if DSN:
        _drop_all(conn, ALL_MODELS)
    conn.close()


async def acall(app, method: str, path: str, *, body: dict | None = None,
                cookie: str | None = None, headers: dict[str, str] | None = None):
    raw_headers = [(b"content-type", b"application/json")]
    if cookie:
        raw_headers.append((b"cookie", f"session={cookie}".encode()))
    for name, value in (headers or {}).items():
        raw_headers.append((name.lower().encode(), value.encode()))
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": b"",
        "headers": raw_headers,
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
    status, _, headers = await acall(
        app, "POST", "/v1/auth/register",
        body={"email": email, "name": name, "password": "password123"},
    )
    assert status == 201, status
    return session_of(headers)


async def top_up(app, email: str, amount: int, payment_id: str):
    """Credit coins the way the gateway would — through the webhook."""
    from settings import WEBHOOK_SECRET

    return await acall(
        app, "POST", "/v1/webhook/payment",
        body={"payment_id": payment_id, "email": email, "amount": amount},
        headers={"X-Webhook-Secret": WEBHOOK_SECRET},
    )
