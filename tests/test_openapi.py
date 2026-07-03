"""OpenAPI schema generation from the route registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from endocore.core.application import Application
from endocore.core.openapi import generate_openapi


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    root = tmp_path_factory.mktemp("oa")

    def write(rel, doc):
        p = root / "Api" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f'"""{doc}"""\nfrom endocore import Response\n'
                     "async def handler(request):\n    return Response.json({})\n", encoding="utf-8")

    write("v1/User/[id]/Get.py", "Fetch a user by id.")
    write("v1/User/Role/Post.py", "Create a role.")
    write("v2/Item/Get.py", "List items.")
    return Application(app_dir=root)


def test_basic_structure(app):
    schema = generate_openapi(app)
    assert schema["openapi"].startswith("3.0")
    assert "info" in schema and "paths" in schema


@pytest.mark.parametrize("path", ["/v1/user/{id}", "/v1/user/role", "/v2/item"])
def test_paths_present(app, path):
    assert path in generate_openapi(app)["paths"]


def test_method_lowercased(app):
    paths = generate_openapi(app)["paths"]
    assert "get" in paths["/v1/user/{id}"]
    assert "post" in paths["/v1/user/role"]


def test_summary_from_docstring(app):
    op = generate_openapi(app)["paths"]["/v1/user/{id}"]["get"]
    assert op["summary"] == "Fetch a user by id."


def test_path_param(app):
    op = generate_openapi(app)["paths"]["/v1/user/{id}"]["get"]
    assert op["parameters"] == [
        {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}
    ]


def test_request_body_for_post(app):
    op = generate_openapi(app)["paths"]["/v1/user/role"]["post"]
    assert "requestBody" in op


def test_no_request_body_for_get(app):
    op = generate_openapi(app)["paths"]["/v1/user/{id}"]["get"]
    assert "requestBody" not in op


def test_tags_are_versions(app):
    op = generate_openapi(app)["paths"]["/v2/item"]["get"]
    assert op["tags"] == ["v2"]


def test_custom_title(app):
    assert generate_openapi(app, title="My API")["info"]["title"] == "My API"


def test_served_endpoints(app):
    import asyncio
    import json

    def call(path):
        scope = {"type": "http", "method": "GET", "path": path, "query_string": b"", "headers": []}

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def main():
            sent = []

            async def send(m):
                sent.append(m)

            await app(scope, receive, send)
            start = next(m for m in sent if m["type"] == "http.response.start")
            body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
            return start["status"], body

        return asyncio.run(main())

    status, body = call("/openapi.json")
    assert status == 200 and "paths" in json.loads(body)
    status2, body2 = call("/docs")
    assert status2 == 200 and b"swagger-ui" in body2
