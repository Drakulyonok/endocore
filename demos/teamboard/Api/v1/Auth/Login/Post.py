"""POST /v1/auth/login — enumeration-safe credential check."""

from endocore import Response, login, verify_password

from Models.core import User
from Services.boards import user_dict


async def handler(request) -> Response:
    body = await request.json() or {}
    email = (body.get("email") or "").strip().lower()
    user = await User.objects.filter(email=email).afirst()
    if not verify_password(body.get("password") or "", user.password_hash if user else None):
        return Response.json({"error": "invalid credentials"}, status=401)
    login(request, user.pk)
    return Response.json(user_dict(user))
