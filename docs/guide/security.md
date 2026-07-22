# Security

Security is a set of **defaults**, not a checklist you bolt on later.

## ORM / SQL injection

- **Values are always bound by the driver** — never string-formatted into SQL.
- **Identifiers** (tables/columns/aliases) are validated (`^[A-Za-z_]\w*$`) and
  quoted; anything else raises `UnsafeIdentifierError`.
- **Lookups are a strict whitelist** — an unknown lookup raises.
- **`LIKE` wildcards** in user input are escaped with an `ESCAPE` clause.
- **`LIMIT`/`OFFSET`** are coerced to integers.

The test suite includes explicit injection tests proving hostile input stays a
bound parameter. See the [ORM](../orm/index.md).

## Log masking

The logging middleware masks sensitive keys **before** writing — see
[Logging](logging.md). Passwords never reach the log stream even though the
middleware sees the raw request.

## Encrypted files at rest

`FileField` encrypts uploads with AES-256-GCM; a leaked storage folder is
unrecoverable without the separate key, and tampering is detected. See
[Encrypted files](../orm/files.md).

## Cookies & CSRF

- `set_signed_cookie` / `get_signed_cookie` use HMAC-SHA256 so cookies can't be
  tampered with.
- `csrf_middleware` implements the signed double-submit-cookie pattern for unsafe
  methods.
- Cookies default to `SameSite=Lax`; set `secure=True`, `httponly=True` as needed.

## Sessions & authentication

Built in, stdlib-only. Sessions travel in an HMAC-signed cookie (stateless, no
store to deploy); passwords are hashed with **scrypt** (`hashlib.scrypt`) in a
self-describing format so work factors can be raised later.

```python
# Middleware/__init__.py
from endocore.middleware import session_middleware
middlewares = [session_middleware(secret=env("SECRET_KEY"), secure=True)]
```

```python
# Api/v1/Login/Post.py
from endocore import Response, login, verify_password
from Models.user import User

async def handler(request):
    body = await request.json()
    user = await User.objects.filter(email=body["email"]).afirst()
    # None still burns a full scrypt run: an unknown email takes as long as a
    # wrong password, so response timing can't enumerate accounts.
    if not verify_password(body["password"], user.password_hash if user else None):
        return Response.json({"error": "invalid credentials"}, status=401)
    login(request, user.pk)                  # stores the pk in the session
    return Response.json({"ok": True})
```

```python
# Api/v1/Me/Get.py — 401 for anonymous requests, via DI
from endocore import Depends, Response, require_user_id

async def handler(request, user_id = Depends(require_user_id)):
    return Response.json({"user_id": user_id})
```

- `hash_password(pw)` → store the string; `verify_password(pw, stored)` is
  constant-time; `needs_rehash(stored)` says when to re-hash after a login.
- `login(request, pk)` / `logout(request)` / `user_id(request)` (→ pk or `None`).
- `request.session` is a plain dict; the cookie is rewritten only when it was
  modified, and deleted when cleared. Keep it small (~4 KB cookie limit).
- A tampered/expired session cookie yields a fresh anonymous session, never a 500.

## Hardening middleware

```python
from endocore.middleware import (
    security_headers_middleware, cors_middleware, rate_limit_middleware,
    proxy_headers_middleware, timeout_middleware, csrf_middleware,
)

middlewares = [
    security_headers_middleware(hsts=True),          # nosniff, DENY frames, HSTS
    cors_middleware(allow_origins=["https://app.example.com"]),
    rate_limit_middleware(limit=100, window=60),
    proxy_headers_middleware(trusted=["10.0.0.1"]),  # trust X-Forwarded-* only from these
    timeout_middleware(seconds=30),
    csrf_middleware(secret="…"),
]
```

## Body-size limit

The app rejects request bodies over `max_body_size` (default 16 MB) with a 413,
protecting against memory-exhaustion uploads.

## Checklist for production

- [ ] Set a strong secret for signed cookies / CSRF (from env, not in code).
- [ ] `configure_storage(key=…)` from a secret manager; back the key up.
- [ ] Enable `security_headers_middleware(hsts=True)` behind TLS.
- [ ] Restrict `cors_middleware(allow_origins=[…])` to your front-ends.
- [ ] Put `proxy_headers_middleware(trusted=[…])` if behind a load balancer.
- [ ] Add `rate_limit_middleware` (or a Redis-backed limiter) on public routes.
- [ ] Run over HTTPS; terminate TLS at your proxy.
