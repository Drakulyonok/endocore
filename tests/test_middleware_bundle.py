"""Coverage for the shipped middleware bundle."""

from __future__ import annotations

import asyncio
import gzip

import pytest

from endocore.core.middleware import build_chain
from endocore.core.request import Request
from endocore.core.response import Response
from endocore.middleware import (
    cors_middleware, csrf_middleware, gzip_middleware, proxy_headers_middleware,
    rate_limit_middleware, security_headers_middleware, timeout_middleware,
)
from endocore.middleware.logging import logging_middleware


def run(mw, *, method="GET", path="/", headers=None, body=b"", client=("1.2.3.4", 0), endpoint=None):
    if endpoint is None:
        async def endpoint(request):
            return Response.json({"ok": True})

    raw_headers = [(k.encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {"type": "http", "method": method, "path": path, "query_string": b"",
             "headers": raw_headers, "client": client}

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    # logging_middleware is outermost in the real app and renders HTTPError -> status.
    pipeline = build_chain([logging_middleware, mw], endpoint)

    async def main():
        request = Request(scope, receive)
        response = await pipeline(request)
        sent = []

        async def send(m):
            sent.append(m)

        await response(send)
        start = next(m for m in sent if m["type"] == "http.response.start")
        out_headers = {k.decode().lower(): v.decode() for k, v in start["headers"]}
        out_body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
        return start["status"], out_headers, out_body

    return asyncio.run(main())


# -- CORS --------------------------------------------------------------------

def test_cors_simple_wildcard():
    _, headers, _ = run(cors_middleware(), headers={"origin": "https://x.com"})
    assert headers["access-control-allow-origin"] == "*"


def test_cors_preflight():
    status, headers, _ = run(
        cors_middleware(allow_origins=["https://x.com"]),
        method="OPTIONS",
        headers={"origin": "https://x.com", "access-control-request-method": "POST"},
    )
    assert status == 204
    assert headers["access-control-allow-origin"] == "https://x.com"
    assert "access-control-allow-methods" in headers


def test_cors_disallowed_origin():
    _, headers, _ = run(cors_middleware(allow_origins=["https://ok.com"]),
                        headers={"origin": "https://evil.com"})
    assert "access-control-allow-origin" not in headers


def test_cors_no_origin():
    _, headers, _ = run(cors_middleware())
    assert "access-control-allow-origin" not in headers


@pytest.mark.parametrize("origin", ["https://a.com", "https://b.com"])
def test_cors_allowlist(origin):
    _, headers, _ = run(cors_middleware(allow_origins=["https://a.com", "https://b.com"]),
                        headers={"origin": origin})
    assert headers["access-control-allow-origin"] == origin


# -- security headers --------------------------------------------------------

@pytest.mark.parametrize("header,value", [
    ("x-content-type-options", "nosniff"),
    ("x-frame-options", "DENY"),
    ("referrer-policy", "no-referrer"),
])
def test_security_headers(header, value):
    _, headers, _ = run(security_headers_middleware())
    assert headers[header] == value


def test_security_hsts_optional():
    _, headers, _ = run(security_headers_middleware(hsts=True))
    assert "strict-transport-security" in headers
    _, headers2, _ = run(security_headers_middleware(hsts=False))
    assert "strict-transport-security" not in headers2


# -- gzip --------------------------------------------------------------------

def test_gzip_compresses_large():
    async def big(request):
        return Response.text("A" * 5000)

    status, headers, body = run(gzip_middleware(minimum_size=100),
                                headers={"accept-encoding": "gzip"}, endpoint=big)
    assert headers.get("content-encoding") == "gzip"
    assert gzip.decompress(body) == b"A" * 5000


def test_gzip_skips_small():
    _, headers, _ = run(gzip_middleware(minimum_size=1000), headers={"accept-encoding": "gzip"})
    assert "content-encoding" not in headers


def test_gzip_skips_without_accept():
    async def big(request):
        return Response.text("A" * 5000)

    _, headers, _ = run(gzip_middleware(minimum_size=100), endpoint=big)
    assert "content-encoding" not in headers


# -- rate limit --------------------------------------------------------------

def test_rate_limit_blocks_after_limit():
    mw = rate_limit_middleware(limit=3, window=60)
    for _ in range(3):
        status, _, _ = run(mw, client=("9.9.9.9", 0))
        assert status == 200
    status, _, _ = run(mw, client=("9.9.9.9", 0))
    assert status == 429


def test_rate_limit_per_ip():
    mw = rate_limit_middleware(limit=1, window=60)
    assert run(mw, client=("1.1.1.1", 0))[0] == 200
    assert run(mw, client=("2.2.2.2", 0))[0] == 200  # different IP, own bucket
    assert run(mw, client=("1.1.1.1", 0))[0] == 429


# -- timeout -----------------------------------------------------------------

def test_timeout_triggers():
    async def slow(request):
        await asyncio.sleep(0.2)
        return Response.json({})

    status, _, _ = run(timeout_middleware(seconds=0.01), endpoint=slow)
    assert status == 504


def test_timeout_allows_fast():
    status, _, _ = run(timeout_middleware(seconds=5))
    assert status == 200


# -- proxy headers -----------------------------------------------------------

def test_proxy_trusted_applies():
    seen = {}

    async def endpoint(request):
        seen["scheme"] = request.scope.get("scheme")
        seen["client"] = request.scope.get("client")
        return Response.json({})

    run(proxy_headers_middleware(trusted=["1.2.3.4"]),
        headers={"x-forwarded-proto": "https", "x-forwarded-for": "9.9.9.9"},
        client=("1.2.3.4", 0), endpoint=endpoint)
    assert seen["scheme"] == "https"
    assert seen["client"][0] == "9.9.9.9"


def test_proxy_untrusted_ignored():
    seen = {}

    async def endpoint(request):
        seen["scheme"] = request.scope.get("scheme")
        return Response.json({})

    run(proxy_headers_middleware(trusted=["10.0.0.1"]),
        headers={"x-forwarded-proto": "https"}, client=("6.6.6.6", 0), endpoint=endpoint)
    assert seen["scheme"] is None


# -- CSRF --------------------------------------------------------------------

def test_csrf_sets_cookie_on_safe():
    status, headers, _ = run(csrf_middleware("secret"), method="GET")
    assert status == 200
    assert "set-cookie" in headers and "csrftoken=" in headers["set-cookie"]


def test_csrf_blocks_unsafe_without_token():
    status, _, _ = run(csrf_middleware("secret"), method="POST")
    assert status == 403


def test_csrf_allows_with_matching_token():
    from endocore.core.signing import Signer

    token = Signer("secret", salt="endocore.csrf").sign("abc")
    status, _, _ = run(csrf_middleware("secret"), method="POST",
                       headers={"cookie": f"csrftoken={token}", "x-csrf-token": token})
    assert status == 200
