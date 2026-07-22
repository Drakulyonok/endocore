"""Cookie sessions — signed, stateless, stdlib-only.

The whole session dict travels in an HMAC-signed cookie, so there is no
server-side store to deploy. Values must be JSON-serializable and the cookie
must stay under ~4 KB — keep sessions small (a user id, a flag), not a cache.

    # Middleware/__init__.py
    from endocore.middleware import session_middleware
    middlewares = [session_middleware(secret=env("SECRET_KEY"))]

Handlers read/write ``request.session``; the cookie is rewritten only when the
session was modified, and deleted when it was cleared.
"""

from __future__ import annotations

from typing import Any

from endocore.core.middleware import Next
from endocore.core.request import Request
from endocore.core.response import Response
from endocore.core.signing import BadSignature, Signer


class Session(dict):
    """A dict that remembers whether it was written to."""

    modified = False

    def _mutate(self) -> None:
        self.modified = True

    def __setitem__(self, key, value) -> None:
        super().__setitem__(key, value)
        self._mutate()

    def __delitem__(self, key) -> None:
        super().__delitem__(key)
        self._mutate()

    def pop(self, *args) -> Any:
        self._mutate()
        return super().pop(*args)

    def clear(self) -> None:
        self._mutate()
        super().clear()

    def update(self, *args, **kwargs) -> None:
        self._mutate()
        super().update(*args, **kwargs)

    def setdefault(self, key, default=None) -> Any:
        if key not in self:
            self._mutate()
        return super().setdefault(key, default)


def session_middleware(
    secret: str,
    *,
    cookie_name: str = "session",
    max_age: int = 14 * 24 * 3600,
    secure: bool = False,
    samesite: str = "lax",
):
    """Attach ``request.session`` and persist it in a signed cookie.

    A tampered or expired cookie yields a fresh empty session (never an error).
    Set ``secure=True`` when serving over HTTPS (recommended in production).
    """
    signer = Signer(secret, salt="endocore.session")

    async def middleware(request: Request, call_next: Next) -> Response:
        data: dict = {}
        raw = request.cookies.get(cookie_name)
        if raw:
            try:
                loaded = signer.loads(raw, max_age=max_age)
                if isinstance(loaded, dict):
                    data = loaded
            except (BadSignature, ValueError):
                pass  # start clean; the old cookie gets overwritten on write
        session = Session(data)
        request.session = session

        response = await call_next(request)

        if session.modified and isinstance(response, Response):
            if session:
                response.set_cookie(
                    cookie_name,
                    signer.dumps(dict(session)),
                    max_age=max_age,
                    httponly=True,
                    secure=secure,
                    samesite=samesite,
                )
            else:
                response.delete_cookie(cookie_name)
        return response

    return middleware
