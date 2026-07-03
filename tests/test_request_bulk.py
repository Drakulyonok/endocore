"""Request parsing: headers, query, cookies, json, form, body limit."""

from __future__ import annotations

import asyncio
import json

import pytest

from endocore.core.exceptions import BadRequest, PayloadTooLarge
from endocore.core.request import Request


def make_request(method="GET", path="/", headers=None, query=b"", body=b"", max_body_size=None):
    raw_headers = [(k.encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {"type": "http", "method": method, "path": path, "query_string": query,
             "headers": raw_headers}

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive, max_body_size=max_body_size)


@pytest.mark.parametrize("query,key,expected", [
    (b"a=1", "a", "1"),
    (b"a=1&b=2", "b", "2"),
    (b"x=hello%20world", "x", "hello world"),
    (b"flag=", "flag", ""),
])
def test_query(query, key, expected):
    assert make_request(query=query).query.get(key) == expected


@pytest.mark.parametrize("headers,key,expected", [
    ({"Content-Type": "application/json"}, "content-type", "application/json"),
    ({"X-Custom": "value"}, "x-custom", "value"),
    ({"AUTHORIZATION": "Bearer x"}, "authorization", "Bearer x"),
])
def test_headers_lowercased(headers, key, expected):
    assert make_request(headers=headers).headers.get(key) == expected


@pytest.mark.parametrize("cookie,key,expected", [
    ("sid=abc", "sid", "abc"),
    ("a=1; b=2", "b", "2"),
    ("token=xyz; sid=123", "token", "xyz"),
    ("", "missing", None),
])
def test_cookies(cookie, key, expected):
    req = make_request(headers={"Cookie": cookie} if cookie else {})
    assert req.cookies.get(key) == expected


@pytest.mark.parametrize("payload", [
    {"a": 1}, {"nested": {"x": [1, 2]}}, [1, 2, 3], {"unicode": "héllo"}, {"bool": True},
])
def test_json(payload):
    body = json.dumps(payload).encode()
    assert asyncio.run(make_request(body=body).json()) == payload


def test_json_empty_is_none():
    assert asyncio.run(make_request(body=b"").json()) is None


def test_json_invalid_raises_badrequest():
    with pytest.raises(BadRequest):
        asyncio.run(make_request(body=b"{not json").json())


@pytest.mark.parametrize("body,field,expected", [
    (b"name=Ada&age=36", "name", "Ada"),
    (b"name=Ada&age=36", "age", "36"),
    (b"x=a%20b", "x", "a b"),
])
def test_form_urlencoded(body, field, expected):
    req = make_request(headers={"Content-Type": "application/x-www-form-urlencoded"}, body=body)
    assert asyncio.run(req.form()).get(field) == expected


def test_form_multipart_and_files():
    boundary = "B"
    body = (
        b"--B\r\nContent-Disposition: form-data; name=\"title\"\r\n\r\nHi\r\n"
        b"--B\r\nContent-Disposition: form-data; name=\"f\"; filename=\"a.txt\"\r\n\r\nDATA\r\n"
        b"--B--\r\n"
    )
    req = make_request(headers={"Content-Type": "multipart/form-data; boundary=B"}, body=body)
    form = asyncio.run(req.form())
    assert form.get("title") == "Hi"
    files = asyncio.run(req.files())
    assert files["f"].read() == b"DATA"


@pytest.mark.parametrize("size,limit,ok", [
    (100, 1000, True), (1000, 1000, True), (1001, 1000, False), (5000, 1000, False),
])
def test_body_size_limit(size, limit, ok):
    req = make_request(body=b"x" * size, max_body_size=limit)
    if ok:
        assert len(asyncio.run(req.body())) == size
    else:
        with pytest.raises(PayloadTooLarge):
            asyncio.run(req.body())


def test_body_cached():
    req = make_request(body=b"hello")
    assert asyncio.run(req.body()) == b"hello"
    assert asyncio.run(req.body()) == b"hello"  # second read from cache


@pytest.mark.parametrize("ctype,expected", [
    ("application/json", "application/json"),
    ("text/plain", "text/plain"),
    ("", ""),
])
def test_content_type(ctype, expected):
    req = make_request(headers={"Content-Type": ctype} if ctype else {})
    assert req.content_type == expected


def test_signed_cookie_roundtrip():
    from endocore.core.response import Response
    from endocore.core.signing import Signer

    token = Signer("secret").sign("session-1")
    req = make_request(headers={"Cookie": f"s={token}"})
    assert req.get_signed_cookie("s", "secret") == "session-1"
    assert req.get_signed_cookie("missing", "secret", default="d") == "d"
