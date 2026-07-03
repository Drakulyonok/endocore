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
