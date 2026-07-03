"""End-to-end Application: DI, providers, background, body limit, versioning."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from endocore.core.application import Application


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    root = tmp_path_factory.mktemp("e2e_app")
    _write(root / "Api" / "v1" / "Ping" / "Get.py",
           "from endocore import Response\n"
           "async def handler(request):\n    return Response.json({'pong': True})\n")
    _write(root / "Api" / "v1" / "Di" / "Get.py",
           "from endocore import Response, Depends\n"
           "def make():\n    return 'injected'\n"
           "async def handler(request, val=Depends(make)):\n"
           "    return Response.json({'val': val})\n")
    _write(root / "Api" / "v1" / "Prov" / "Get.py",
           "from endocore import Response\n"
           "async def handler(request, service):\n"
           "    return Response.json({'svc': service})\n")
    _write(root / "Api" / "v1" / "Echo" / "Post.py",
           "from endocore import Response\n"
           "async def handler(request):\n"
           "    return Response.json(await request.json())\n")
    _write(root / "providers.py", "providers = {'service': lambda: 'SVC'}\n")
    return Application(app_dir=root, max_body_size=50)


def call(app, method, path, *, body=b"", headers=None):
    scope = {"type": "http", "method": method, "path": path, "query_string": b"",
             "headers": [(k.encode(), v.encode()) for k, v in (headers or {}).items()]}

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def main():
        sent = []

        async def send(m):
            sent.append(m)

        await app(scope, receive, send)
        start = next(m for m in sent if m["type"] == "http.response.start")
        out = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
        return start["status"], out

    return asyncio.run(main())


def test_ping(app):
    status, body = call(app, "GET", "/v1/ping")
    assert status == 200 and json.loads(body) == {"pong": True}


def test_di_depends(app):
    status, body = call(app, "GET", "/v1/di")
    assert status == 200 and json.loads(body) == {"val": "injected"}


def test_provider_injection(app):
    status, body = call(app, "GET", "/v1/prov")
    assert status == 200 and json.loads(body) == {"svc": "SVC"}


@pytest.mark.parametrize("payload", [{"a": 1}, {"x": "y"}, {"n": 42}])
def test_echo_small_body(app, payload):
    body = json.dumps(payload).encode()
    status, out = call(app, "POST", "/v1/echo", body=body)
    assert status == 200 and json.loads(out) == payload


def test_body_limit(app):
    big = json.dumps({"data": "x" * 200}).encode()
    status, _ = call(app, "POST", "/v1/echo", body=big)
    assert status == 413


def test_request_id_header(app):
    scope = {"type": "http", "method": "GET", "path": "/v1/ping", "query_string": b"", "headers": []}

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def main():
        sent = []

        async def send(m):
            sent.append(m)

        await app(scope, receive, send)
        start = next(m for m in sent if m["type"] == "http.response.start")
        return {k.decode().lower(): v.decode() for k, v in start["headers"]}

    headers = asyncio.run(main())
    assert "x-request-id" in headers


def test_404_and_405(app):
    assert call(app, "GET", "/v1/nope")[0] == 404
    assert call(app, "DELETE", "/v1/ping")[0] == 405
    assert call(app, "GET", "/ping")[0] == 404  # no version prefix


def test_default_version_alias(tmp_path_factory):
    root = tmp_path_factory.mktemp("ver_app")
    _write(root / "Api" / "v1" / "Health" / "Get.py",
           "from endocore import Response\n"
           "async def handler(request):\n    return Response.json({'ok': True})\n")
    strict = Application(app_dir=root)
    assert call(strict, "GET", "/health")[0] == 404
    lenient = Application(app_dir=root, default_version="latest")
    assert call(lenient, "GET", "/health")[0] == 200
