"""End-to-end ASGI behaviour against the bundled example app."""

from __future__ import annotations

import json

from tests.conftest import call


def test_get_static_route(app):
    status, body, _ = call(app, "GET", "/v1/user/role")
    assert status == 200
    assert json.loads(body) == {"roles": ["admin", "editor", "viewer"]}


def test_dynamic_segment(app):
    status, body, _ = call(app, "GET", "/v1/user/42")
    assert status == 200
    assert json.loads(body) == {"id": "42", "name": "user-42"}


def test_post_calls_service(app):
    body_in = json.dumps({"name": "admin", "password": "secret"}).encode()
    status, body, _ = call(app, "POST", "/v1/user/role", body=body_in)
    assert status == 201
    assert json.loads(body) == {"name": "admin", "created": True}


def test_no_version_is_404(app):
    status, _, _ = call(app, "GET", "/user/role")
    assert status == 404


def test_method_not_allowed_sets_allow_header(app):
    status, _, headers = call(app, "DELETE", "/v1/user/role")
    assert status == 405
    assert set(headers["allow"].split(", ")) == {"GET", "POST"}


def test_http_error_from_handler(app):
    status, body, _ = call(app, "GET", "/v1/user/0")
    assert status == 404
    assert json.loads(body) == {"error": "user not found"}


def test_user_middleware_runs(app):
    # The example registers request_id_middleware.
    _, _, headers = call(app, "GET", "/v1/user/role")
    assert "x-request-id" in headers


def test_middleware_wired(app):
    # logging + request_id
    assert len(app.middlewares) == 2
