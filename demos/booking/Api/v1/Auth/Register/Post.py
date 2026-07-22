"""POST /v1/auth/register — create an account and log in."""

from endocore import Conflict, Response, UnprocessableEntity, hash_password, login

from Models.core import User


async def handler(request) -> Response:
    body = await request.json() or {}
    email = (body.get("email") or "").strip().lower()
    name = (body.get("name") or "").strip()
    password = body.get("password") or ""
    if not email or "@" not in email or not name or len(password) < 8:
        raise UnprocessableEntity("email, name and a password of 8+ chars are required")

    if await User.objects.filter(email=email).aexists():
        raise Conflict("email already registered")
    user = await User.objects.acreate(
        email=email, name=name, password_hash=hash_password(password)
    )
    login(request, user.pk)
    return Response.json({"id": user.pk, "email": user.email, "name": user.name}, status=201)
