"""HTTP exception classes: status + detail + rendering through the app."""

from __future__ import annotations

import json

import pytest

from endocore.core.exceptions import (
    BadRequest, Conflict, Forbidden, HTTPError, MethodNotAllowed, NotFound,
    PayloadTooLarge, PermissionDenied, TooManyRequests, Unauthorized, UnprocessableEntity,
)

CLASSES = [
    (BadRequest, 400, "Bad Request"),
    (Unauthorized, 401, "Unauthorized"),
    (Forbidden, 403, "Forbidden"),
    (NotFound, 404, "Not Found"),
    (MethodNotAllowed, 405, "Method Not Allowed"),
    (Conflict, 409, "Conflict"),
    (PayloadTooLarge, 413, "Payload Too Large"),
    (UnprocessableEntity, 422, "Unprocessable Entity"),
    (TooManyRequests, 429, "Too Many Requests"),
]


@pytest.mark.parametrize("cls,status,message", CLASSES)
def test_default_status_and_message(cls, status, message):
    exc = cls()
    assert exc.status == status
    assert exc.detail == message
    assert isinstance(exc, HTTPError)


@pytest.mark.parametrize("cls,status,message", CLASSES)
def test_custom_detail(cls, status, message):
    exc = cls("custom message")
    assert exc.status == status
    assert exc.detail == "custom message"


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 418, 422, 429, 500, 503])
def test_httperror_explicit_status(status):
    exc = HTTPError(status, "detail")
    assert exc.status == status and exc.detail == "detail"


def test_permission_denied_is_forbidden():
    assert PermissionDenied is Forbidden
    assert PermissionDenied().status == 403


@pytest.mark.parametrize("cls,status,message", CLASSES)
def test_raised_render(app_call, cls, status, message):
    # app_call fixture builds a tiny app whose handler raises the exception.
    got_status, body = app_call(cls)
    assert got_status == status
    assert json.loads(body)["error"] == message


@pytest.fixture()
def app_call():
    import asyncio
    from endocore.core.middleware import build_chain
    from endocore.middleware.logging import logging_middleware
    from endocore.core.request import Request
    from endocore.core.response import Response

    def run(exc_cls):
        async def endpoint(request):
            raise exc_cls()

        pipeline = build_chain([logging_middleware], endpoint)
        scope = {"type": "http", "method": "GET", "path": "/x", "query_string": b"", "headers": []}

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def main():
            request = Request(scope, receive)
            response = await pipeline(request)
            sent = []

            async def send(m):
                sent.append(m)

            await response(send)
            start = next(m for m in sent if m["type"] == "http.response.start")
            body = next(m for m in sent if m["type"] == "http.response.body")["body"]
            return start["status"], body

        return asyncio.run(main())

    return run
