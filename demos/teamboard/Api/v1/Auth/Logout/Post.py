"""POST /v1/auth/logout."""

from endocore import Response, logout


async def handler(request) -> Response:
    logout(request)
    return Response.json({"ok": True})
