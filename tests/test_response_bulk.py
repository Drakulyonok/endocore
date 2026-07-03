"""Response rendering, cookies, redirect, streaming."""

from __future__ import annotations

import asyncio
import json

import pytest

from endocore.core.response import Response, StreamingResponse


def emit(response):
    sent = []

    async def send(m):
        sent.append(m)

    asyncio.run(response(send))
    start = next(m for m in sent if m["type"] == "http.response.start")
    headers = [(k.decode(), v.decode()) for k, v in start["headers"]]
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return start["status"], headers, body


@pytest.mark.parametrize("content,expected", [
    ({"a": 1}, b'{"a": 1}'),
    ([1, 2, 3], b"[1, 2, 3]"),
    (42, b"42"),
    (True, b"true"),
    (None, b""),
])
def test_json_render(content, expected):
    _, _, body = emit(Response.json(content))
    assert body == expected


@pytest.mark.parametrize("status", [200, 201, 204, 301, 400, 404, 500])
def test_status_codes(status):
    got, _, _ = emit(Response(None, status=status))
    assert got == status


@pytest.mark.parametrize("text", ["", "hello", "unicode héllo", "🚀", "x" * 1000])
def test_text_render(text):
    _, headers, body = emit(Response.text(text))
    assert body == text.encode()
    assert any(k == "content-type" and "text/plain" in v for k, v in headers)


def test_content_length_set():
    _, headers, body = emit(Response.json({"k": "v"}))
    length = next(v for k, v in headers if k == "content-length")
    assert int(length) == len(body)


@pytest.mark.parametrize("name,value", [("sid", "abc"), ("token", "xyz"), ("k", "")])
def test_set_cookie(name, value):
    r = Response.json({}).set_cookie(name, value)
    _, headers, _ = emit(r)
    cookies = [v for k, v in headers if k == "set-cookie"]
    assert any(c.startswith(f"{name}={value}") for c in cookies)


@pytest.mark.parametrize("kwargs,fragment", [
    ({"httponly": True}, "HttpOnly"),
    ({"secure": True}, "Secure"),
    ({"samesite": "strict"}, "SameSite=Strict"),
    ({"max_age": 60}, "Max-Age=60"),
    ({"path": "/api"}, "Path=/api"),
    ({"domain": "x.com"}, "Domain=x.com"),
])
def test_cookie_attributes(kwargs, fragment):
    r = Response.json({}).set_cookie("k", "v", **kwargs)
    _, headers, _ = emit(r)
    cookie = next(v for k, v in headers if k == "set-cookie")
    assert fragment in cookie


def test_delete_cookie():
    r = Response.json({}).delete_cookie("sid")
    _, headers, _ = emit(r)
    cookie = next(v for k, v in headers if k == "set-cookie")
    assert "sid=" in cookie and "Max-Age=0" in cookie


def test_multiple_cookies():
    r = Response.json({}).set_cookie("a", "1").set_cookie("b", "2")
    _, headers, _ = emit(r)
    cookies = [v for k, v in headers if k == "set-cookie"]
    assert len(cookies) == 2


@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_redirect(status):
    got, headers, _ = emit(Response.redirect("/new", status=status))
    assert got == status
    assert any(k.lower() == "location" and v == "/new" for k, v in headers)


def test_no_content():
    got, _, body = emit(Response.no_content())
    assert got == 204 and body == b""


@pytest.mark.parametrize("chunks", [
    [b"a", b"b", b"c"],
    ["x", "y"],
    [b"one"],
    [b"" ],
])
def test_streaming_sync(chunks):
    _, _, body = emit(StreamingResponse(chunks))
    expected = b"".join(c.encode() if isinstance(c, str) else c for c in chunks)
    assert body == expected


def test_streaming_async():
    async def gen():
        for i in range(5):
            yield f"{i}".encode()

    _, _, body = emit(StreamingResponse(gen()))
    assert body == b"01234"


@pytest.mark.parametrize("headers", [{"X-A": "1"}, {"X-A": "1", "X-B": "2"}])
def test_custom_headers(headers):
    _, out, _ = emit(Response.json({}, headers=headers))
    for k, v in headers.items():
        assert any(hk.lower() == k.lower() and hv == v for hk, hv in out)
