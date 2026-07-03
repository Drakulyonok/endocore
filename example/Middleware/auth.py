"""Example user middleware: reject requests without a valid token.

Middleware is ``(request, call_next) -> Response``; return an early Response to
short-circuit (auth) or await ``call_next`` to pass control inward.
"""

from endocore import Request, Response
from Services.auth_service import authenticate


async def auth_middleware(request: Request, call_next):
    user = authenticate(request.headers.get("authorization"))
    if user is None:
        return Response.json({"error": "unauthorized"}, status=401)
    request.scope["user"] = user
    return await call_next(request)
