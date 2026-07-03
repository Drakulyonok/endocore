"""CSRF protection via the signed double-submit-cookie pattern.

On safe requests a signed CSRF cookie is issued. On unsafe requests (POST/PUT/
PATCH/DELETE) the ``X-CSRF-Token`` header must match the cookie and verify.
"""

from __future__ import annotations

from uuid import uuid4

from endocore.core.exceptions import Forbidden
from endocore.core.middleware import Next
from endocore.core.request import Request
from endocore.core.response import Response
from endocore.core.signing import BadSignature, Signer

_SAFE = {"GET", "HEAD", "OPTIONS", "TRACE"}


def csrf_middleware(secret: str, *, cookie_name: str = "csrftoken", header_name: str = "x-csrf-token"):
    signer = Signer(secret, salt="endocore.csrf")

    async def middleware(request: Request, call_next: Next) -> Response:
        if request.method in _SAFE:
            response = await call_next(request)
            if isinstance(response, Response) and cookie_name not in request.cookies:
                response.set_cookie(
                    cookie_name, signer.sign(uuid4().hex), httponly=False, samesite="lax"
                )
            return response

        cookie = request.cookies.get(cookie_name)
        header = request.headers.get(header_name)
        if not cookie or not header or cookie != header:
            raise Forbidden("CSRF token missing or mismatched")
        try:
            signer.unsign(cookie)
        except BadSignature:
            raise Forbidden("CSRF token invalid") from None
        return await call_next(request)

    return middleware
