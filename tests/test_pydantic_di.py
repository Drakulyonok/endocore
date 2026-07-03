"""Pydantic request-body validation via DI + OpenAPI schema."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

pytest.importorskip("pydantic")

from pydantic import BaseModel  # noqa: E402

from endocore.core.application import Application  # noqa: E402
from endocore.core.di import is_pydantic_model, solve  # noqa: E402
from endocore.core.openapi import generate_openapi  # noqa: E402


class Payload(BaseModel):
    name: str
    age: int


def test_is_pydantic_model():
    assert is_pydantic_model(Payload) is True
    assert is_pydantic_model(dict) is False
    assert is_pydantic_model(int) is False


class FakeRequest:
    def __init__(self, body):
        self._body = body
        self.path_params = {}

    async def json(self):
        return self._body


def test_di_validates_body():
    async def handler(request, data: Payload):
        return data

    kwargs = asyncio.run(solve(handler, FakeRequest({"name": "Ada", "age": 36}), None))
    assert isinstance(kwargs["data"], Payload)
    assert kwargs["data"].name == "Ada" and kwargs["data"].age == 36


def test_di_invalid_body_raises_422():
    from endocore.core.exceptions import UnprocessableEntity

    async def handler(request, data: Payload):
        return data

    with pytest.raises(UnprocessableEntity):
        asyncio.run(solve(handler, FakeRequest({"name": "Ada", "age": "notint"}), None))


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    root = tmp_path_factory.mktemp("pyd")
    (root / "Api" / "v1" / "User").mkdir(parents=True)
    (root / "Api" / "v1" / "User" / "Post.py").write_text(
        '"""Create a user."""\n'
        "from endocore import Response\n"
        "from pydantic import BaseModel\n"
        "class UserIn(BaseModel):\n    name: str\n    age: int\n"
        "async def handler(request, data: UserIn) -> Response:\n"
        "    return Response.json({'name': data.name, 'age': data.age}, status=201)\n",
        encoding="utf-8",
    )
    return Application(app_dir=root)


def _post(app, path, body):
    scope = {"type": "http", "method": "POST", "path": path, "query_string": b"",
             "headers": [(b"content-type", b"application/json")]}

    async def receive():
        return {"type": "http.request", "body": json.dumps(body).encode(), "more_body": False}

    async def main():
        sent = []

        async def send(m):
            sent.append(m)

        await app(scope, receive, send)
        start = next(m for m in sent if m["type"] == "http.response.start")
        out = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
        return start["status"], out

    return asyncio.run(main())


def test_endpoint_valid(app):
    status, body = _post(app, "/v1/user", {"name": "Ada", "age": 36})
    assert status == 201 and json.loads(body) == {"name": "Ada", "age": 36}


def test_endpoint_invalid(app):
    status, body = _post(app, "/v1/user", {"name": "Ada", "age": "x"})
    assert status == 422
    assert isinstance(json.loads(body)["error"], list)


def test_openapi_includes_model_schema(app):
    schema = generate_openapi(app)
    body = schema["paths"]["/v1/user"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert body["properties"]["name"]["type"] == "string"
    assert body["properties"]["age"]["type"] == "integer"
