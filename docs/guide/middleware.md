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
| `rate_limit_middleware(limit=, window=, redis_client=)` | fixed-window rate limit (429); in-memory per-process by default, or a shared limit across every worker with `redis_client=` |
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

### Sharing the rate limit across workers

The plain in-memory limiter counts **per process** — run 4 Gunicorn workers
and each enforces its own independent 100-req/min bucket, so the *real*
limit for a client is 400/min, not 100. Pass a Redis client to share one
counter (Redis `INCR` is atomic, so concurrent workers can't race each other
into under-counting):

```python
from endocore.extensions import redis_client
from endocore.middleware import rate_limit_middleware

middlewares = [
    rate_limit_middleware(limit=100, window=60, redis_client=redis_client(url="redis://localhost:6379/0")),
]
```

The Redis client's calls are synchronous (redis-py), so they're offloaded to
a worker thread automatically — a slow or briefly-unreachable Redis can't
stall the event loop for other in-flight requests.

## The always-on logging layer

The framework's own logging middleware is always the outermost layer. It:

- times every request and logs it (`[INFO] POST /v1/user/role 201 3ms id=…`),
- attaches an `X-Request-ID` (honouring an inbound one),
- **masks sensitive keys** in the logged payload,
- turns any raised [HTTP exception](exceptions.md) into its status, and any
  other exception into a 500 (with a traceback in the logs).
