# Middleware

A middleware is a function that every request passes through before your
handler — and every response passes through after it. It's the place for things
that apply to all endpoints at once: auth checks, CORS, rate limits, timing.

The layers wrap the handler like an onion: each middleware gets the `Request`
and a `call_next`, and either returns a response early or passes control
inward.

```python
from endocore import Request, Response

async def timing_middleware(request: Request, call_next):
    import time
    start = time.perf_counter()
    response = await call_next(request)          # inward
    ms = (time.perf_counter() - start) * 1000
    response.headers["X-Elapsed-ms"] = f"{ms:.1f}"
    return response
```

## Registering middleware

List them, ordered, in `Middleware/__init__.py`. The **first is outermost**
(just inside the framework's logging middleware).

```python
# Middleware/__init__.py
from endocore.middleware import cors_middleware, security_headers_middleware
from Middleware.auth import auth_middleware

middlewares = [
    cors_middleware(allow_origins=["https://app.example.com"]),
    security_headers_middleware(),
    auth_middleware,
]
```

## Short-circuiting

Return a `Response` (or raise an [HTTP exception](exceptions.md)) to stop before
the handler:

```python
from endocore import Request, Response, Unauthorized

async def auth_middleware(request: Request, call_next):
    if not request.headers.get("authorization"):
        raise Unauthorized("missing token")      # rendered as 401
    return await call_next(request)
```

## Shipped middleware

Import from `endocore.middleware`:

| Factory | Purpose |
|---------|---------|
| `cors_middleware(...)` | CORS headers + preflight |
| `security_headers_middleware(...)` | `X-Content-Type-Options`, `X-Frame-Options`, HSTS, … |
| `gzip_middleware(...)` | gzip compression for large responses |
| `proxy_headers_middleware(...)` | honour `X-Forwarded-*` from trusted proxies |
| `rate_limit_middleware(limit=, window=)` | in-memory fixed-window rate limit (429) |
| `timeout_middleware(seconds=)` | abort slow requests with 504 |
| `csrf_middleware(secret)` | signed double-submit-cookie CSRF |

```python
from endocore.middleware import (
    cors_middleware, gzip_middleware, rate_limit_middleware, csrf_middleware,
)

middlewares = [
    cors_middleware(allow_origins=["*"]),
    gzip_middleware(minimum_size=500),
    rate_limit_middleware(limit=100, window=60),
    csrf_middleware(secret="change-me"),
]
```

## The always-on logging layer

The framework's own logging middleware is always the outermost layer. It:

- times every request and logs it (`[INFO] POST /v1/user/role 201 3ms id=…`),
- attaches an `X-Request-ID` (honouring an inbound one),
- **masks sensitive keys** in the logged payload,
- turns any raised [HTTP exception](exceptions.md) into its status, and any
  other exception into a 500 (with a traceback in the logs).
