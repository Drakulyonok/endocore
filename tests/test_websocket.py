"""WebSocket class + application dispatch."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from endocore.core.application import Application
from endocore.core.websocket import WebSocket, WebSocketDisconnect


def drive(incoming):
    """Return (websocket, sent, run) driving a WebSocket over fake ASGI messages."""
    inbox = list(incoming)
    sent = []

    async def receive():
        return inbox.pop(0)

    async def send(m):
        sent.append(m)

    scope = {"type": "websocket", "path": "/ws", "query_string": b"page=1", "headers": [(b"x-test", b"1")]}
    return WebSocket(scope, receive, send), sent


def test_accept():
    ws, sent = drive([{"type": "websocket.connect"}])
    asyncio.run(ws.accept())
    assert sent == [{"type": "websocket.accept", "subprotocol": None}]
    assert ws.accepted


def test_receive_text():
    ws, _ = drive([{"type": "websocket.connect"}, {"type": "websocket.receive", "text": "hi"}])
    asyncio.run(ws.accept())
    assert asyncio.run(ws.receive_text()) == "hi"


def test_receive_json():
    ws, _ = drive([{"type": "websocket.connect"}, {"type": "websocket.receive", "text": '{"a": 1}'}])
    asyncio.run(ws.accept())
    assert asyncio.run(ws.receive_json()) == {"a": 1}


def test_send_text_bytes_json():
    ws, sent = drive([{"type": "websocket.connect"}])
    asyncio.run(ws.accept())
    asyncio.run(ws.send_text("hello"))
    asyncio.run(ws.send_bytes(b"\x00\x01"))
    asyncio.run(ws.send_json({"k": "v"}))
    payloads = [m for m in sent if m["type"] == "websocket.send"]
    assert payloads[0]["text"] == "hello"
    assert payloads[1]["bytes"] == b"\x00\x01"
    assert json.loads(payloads[2]["text"]) == {"k": "v"}


def test_disconnect_raises():
    ws, _ = drive([{"type": "websocket.connect"}, {"type": "websocket.disconnect", "code": 1001}])
    asyncio.run(ws.accept())
    with pytest.raises(WebSocketDisconnect):
        asyncio.run(ws.receive())


def test_query_and_headers():
    ws, _ = drive([{"type": "websocket.connect"}])
    assert ws.query.get("page") == "1"
    assert ws.headers.get("x-test") == "1"


def test_close():
    ws, sent = drive([{"type": "websocket.connect"}])
    asyncio.run(ws.close(4000))
    assert sent[-1] == {"type": "websocket.close", "code": 4000}


# -- application dispatch ----------------------------------------------------

@pytest.fixture(scope="module")
def ws_app(tmp_path_factory):
    root = tmp_path_factory.mktemp("ws")
    (root / "Api" / "v1" / "Echo").mkdir(parents=True)
    (root / "Api" / "v1" / "Echo" / "Socket.py").write_text(
        "async def handler(websocket):\n"
        "    await websocket.accept()\n"
        "    async for m in websocket.iter_text():\n"
        "        await websocket.send_text('echo:' + m)\n",
        encoding="utf-8",
    )
    return Application(app_dir=root)


def _run_ws(app, path, messages):
    inbox = list(messages)
    sent = []

    async def receive():
        return inbox.pop(0)

    async def send(m):
        sent.append(m)

    scope = {"type": "websocket", "path": path, "query_string": b"", "headers": []}
    asyncio.run(app(scope, receive, send))
    return sent


def test_ws_echo(ws_app):
    sent = _run_ws(ws_app, "/v1/echo", [
        {"type": "websocket.connect"},
        {"type": "websocket.receive", "text": "a"},
        {"type": "websocket.receive", "text": "b"},
        {"type": "websocket.disconnect", "code": 1000},
    ])
    texts = [m["text"] for m in sent if m["type"] == "websocket.send"]
    assert texts == ["echo:a", "echo:b"]
    assert sent[0]["type"] == "websocket.accept"


def test_ws_unknown_route_rejected(ws_app):
    sent = _run_ws(ws_app, "/v1/nope", [{"type": "websocket.connect"}])
    assert sent == [{"type": "websocket.close", "code": 4404}]


# -- origin checks (cross-site websocket hijacking) ---------------------------


def _run_ws_with_headers(app, path, headers, messages):
    inbox = list(messages)
    sent = []

    async def receive():
        return inbox.pop(0)

    async def send(m):
        sent.append(m)

    scope = {"type": "websocket", "path": path, "query_string": b"", "headers": headers}
    asyncio.run(app(scope, receive, send))
    return sent


def test_ws_cross_site_origin_rejected_by_default(ws_app):
    """A page on attacker.com opening a websocket to this app must not
    succeed even though the browser would attach this app's cookies."""
    sent = _run_ws_with_headers(
        ws_app, "/v1/echo",
        [(b"host", b"example.com"), (b"origin", b"https://attacker.com")],
        [{"type": "websocket.connect"}],
    )
    assert sent == [{"type": "websocket.close", "code": 4403}]


def test_ws_same_origin_allowed_by_default(ws_app):
    sent = _run_ws_with_headers(
        ws_app, "/v1/echo",
        [(b"host", b"example.com"), (b"origin", b"https://example.com"),
         (b"x-test", b"1")],
        [{"type": "websocket.connect"}, {"type": "websocket.disconnect", "code": 1000}],
    )
    assert sent[0]["type"] == "websocket.accept"


def test_ws_no_origin_header_allowed_by_default(ws_app):
    """Non-browser clients (curl, another service, a native app) don't send
    Origin at all — nothing to hijack a browser session from."""
    sent = _run_ws_with_headers(
        ws_app, "/v1/echo",
        [(b"host", b"example.com")],
        [{"type": "websocket.connect"}, {"type": "websocket.disconnect", "code": 1000}],
    )
    assert sent[0]["type"] == "websocket.accept"


def test_ws_dev_mode_does_not_enforce_same_origin_by_default(tmp_path_factory):
    """A local frontend on a different port (e.g. :3000 talking to a
    dev=True backend on :8000) is a different origin — same-origin
    enforcement must not be the default in dev, or local dev breaks."""
    from endocore.core.application import Application

    root = tmp_path_factory.mktemp("ws-dev")
    (root / "Api" / "v1" / "Echo").mkdir(parents=True)
    (root / "Api" / "v1" / "Echo" / "Socket.py").write_text(
        "async def handler(websocket):\n    await websocket.accept()\n", encoding="utf-8"
    )
    app = Application(app_dir=root, dev=True)
    sent = _run_ws_with_headers(
        app, "/v1/echo",
        [(b"host", b"localhost:8000"), (b"origin", b"http://localhost:3000")],
        [{"type": "websocket.connect"}],
    )
    assert sent[0]["type"] == "websocket.accept"


def test_ws_dev_mode_still_honours_an_explicit_allowlist(tmp_path_factory):
    from endocore.core.application import Application

    root = tmp_path_factory.mktemp("ws-dev-explicit")
    (root / "Api" / "v1" / "Echo").mkdir(parents=True)
    (root / "Api" / "v1" / "Echo" / "Socket.py").write_text(
        "async def handler(websocket):\n    await websocket.accept()\n", encoding="utf-8"
    )
    app = Application(app_dir=root, dev=True, ws_allowed_origins=["http://localhost:3000"])
    blocked = _run_ws_with_headers(
        app, "/v1/echo",
        [(b"host", b"localhost:8000"), (b"origin", b"https://attacker.com")],
        [{"type": "websocket.connect"}],
    )
    assert blocked == [{"type": "websocket.close", "code": 4403}]


def test_ws_allowed_origins_wildcard_disables_check(tmp_path_factory):
    from endocore.core.application import Application

    root = tmp_path_factory.mktemp("ws-wildcard")
    (root / "Api" / "v1" / "Echo").mkdir(parents=True)
    (root / "Api" / "v1" / "Echo" / "Socket.py").write_text(
        "async def handler(websocket):\n    await websocket.accept()\n", encoding="utf-8"
    )
    app = Application(app_dir=root, ws_allowed_origins="*")
    sent = _run_ws_with_headers(
        app, "/v1/echo",
        [(b"host", b"example.com"), (b"origin", b"https://attacker.com")],
        [{"type": "websocket.connect"}],
    )
    assert sent[0]["type"] == "websocket.accept"


def test_ws_allowed_origins_explicit_list(tmp_path_factory):
    from endocore.core.application import Application

    root = tmp_path_factory.mktemp("ws-allowlist")
    (root / "Api" / "v1" / "Echo").mkdir(parents=True)
    (root / "Api" / "v1" / "Echo" / "Socket.py").write_text(
        "async def handler(websocket):\n    await websocket.accept()\n", encoding="utf-8"
    )
    app = Application(app_dir=root, ws_allowed_origins=["https://trusted-frontend.com"])

    allowed = _run_ws_with_headers(
        app, "/v1/echo",
        [(b"host", b"example.com"), (b"origin", b"https://trusted-frontend.com")],
        [{"type": "websocket.connect"}],
    )
    assert allowed[0]["type"] == "websocket.accept"

    blocked = _run_ws_with_headers(
        app, "/v1/echo",
        [(b"host", b"example.com"), (b"origin", b"https://example.com")],  # same-origin, but not in the explicit list
        [{"type": "websocket.connect"}],
    )
    assert blocked == [{"type": "websocket.close", "code": 4403}]
