"""Session-based authentication helpers.

Builds on :func:`~endocore.middleware.session_middleware` and DI — no new
concepts. The session stores only the user's pk (under ``_user_id``); loading
the user row stays in your code, where it belongs.

    # Api/v1/Login/Post.py
    from endocore import Response, login, verify_password
    from Models.user import User

    async def handler(request):
        body = await request.json()
        user = await User.objects.filter(email=body["email"]).afirst()
        # None still burns a scrypt run: timing can't enumerate accounts.
        if not verify_password(body["password"], user.password_hash if user else None):
            return Response.json({"error": "invalid credentials"}, status=401)
        login(request, user.pk)
        return Response.json({"ok": True})

    # Api/v1/Me/Get.py — 401 for anonymous requests, via DI
    from endocore import Depends, Response, require_user_id

    async def handler(request, user_id = Depends(require_user_id)):
        return Response.json({"user_id": user_id})
"""

from __future__ import annotations

from typing import Any

from endocore.core.exceptions import EndoCoreError, Unauthorized
from endocore.core.request import Request

__all__ = ["SESSION_KEY", "login", "logout", "user_id", "require_user_id"]

SESSION_KEY = "_user_id"


def _session(request: Request) -> dict:
    session = getattr(request, "session", None)
    if session is None:
        raise EndoCoreError(
            "request has no session — add session_middleware(secret=...) to "
            "Middleware/__init__.py before using auth helpers"
        )
    return session


def login(request: Request, user_pk: Any) -> None:
    """Record the authenticated user's pk in the session."""
    session = _session(request)
    session.clear()  # drop any stale state from a previous identity
    session[SESSION_KEY] = user_pk


def logout(request: Request) -> None:
    """Forget the authenticated user (clears the whole session)."""
    _session(request).clear()


def user_id(request: Request) -> Any | None:
    """The logged-in user's pk, or ``None`` for anonymous requests."""
    session = getattr(request, "session", None)
    return None if session is None else session.get(SESSION_KEY)


def require_user_id(request: Request) -> Any:
    """DI dependency: the logged-in user's pk, or **401** for anonymous.

    Use as ``user_id = Depends(require_user_id)`` in a handler signature.
    """
    value = user_id(request)
    if value is None:
        raise Unauthorized("authentication required")
    return value
