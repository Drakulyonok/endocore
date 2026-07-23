# Security

Security is a set of **defaults**, not a checklist you bolt on later. Every
item below either fails closed automatically, or ships as an explicit,
one-line opt-in — nothing here needs a security team to turn on.

This page is organized in three parts: what the framework **already
protects you from** (no action needed), the **hardening toolkit** you wire in
yourself for your specific deployment, and the handful of things that are
**inherently your call**, because the framework has no way to know your
intent.

## Built in — nothing to configure

### SQL injection

- **Values are always bound by the driver** — never string-formatted into SQL.
- **Identifiers** (tables/columns/aliases) are validated (`^[A-Za-z_]\w*$`) and
  quoted; anything else raises `UnsafeIdentifierError`.
- **Lookups are a strict whitelist** — an unknown lookup raises.
- **`LIKE` wildcards** in user input are escaped with an `ESCAPE` clause.
- **`LIMIT`/`OFFSET`** are coerced to integers.

!!! tip "Proven, not just claimed"
    The test suite includes explicit injection tests asserting hostile input
    stays a bound parameter — see the [ORM](../orm/index.md). CI also runs
    `bandit` against the ORM's SQL-building code on every push (see
    [Continuous scanning](#continuous-scanning) below).

### Response header & cookie injection

`Response` rejects (raises `ValueError`) any header name, header value, cookie
component, or `media_type` containing a raw CR, LF, or NUL — the classic
"HTTP response splitting" primitive (CWE-113). Enforced unconditionally at the
point the response is built, for both `Response` and `StreamingResponse` —
never left to the ASGI server to catch.

### Log & repr masking

- The logging middleware masks sensitive keys **before** writing — see
  [Logging](logging.md). Matching is by substring, case/separator-insensitive,
  so `old_password`, `X-Api-Key`, and `refresh_token` are all caught, not just
  a field literally named `password`.
- `Model.__repr__` masks fields whose name looks secret-shaped the same way —
  a `password_hash` column doesn't end up readable in a stray `print(user)`,
  a traceback, or a debugger.

### Encrypted files at rest

`FileField` encrypts uploads with AES-256-GCM; a leaked storage folder is
unrecoverable without the separate key, and tampering is detected. See
[Encrypted files](../orm/files.md).

### Cookies & CSRF

- `set_signed_cookie` / `get_signed_cookie` use HMAC-SHA256 so cookies can't be
  tampered with.
- `csrf_middleware` implements the signed double-submit-cookie pattern for
  unsafe methods, comparing the cookie and header in constant time.
- Cookies default to `SameSite=Lax`; set `secure=True`, `httponly=True` as
  needed.

### Sessions & authentication

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

### WebSockets (cross-site hijacking)

The handshake enforces same-origin by default outside `dev=True` — a page on
another site opening a websocket to your app doesn't get to ride along on a
cookie-based session just because the browser attaches cookies to the
connection (cross-site websocket hijacking). Configure it explicitly for a
real cross-origin frontend, same shape as `cors_middleware`:

```python
app = Application(ws_allowed_origins=["https://app.example.com"])
```

`ws_allowed_origins="*"` disables the check; leaving it unset only relaxes it
automatically in `dev=True` (a local frontend on a different port is a
different origin, and same-origin would otherwise reject every local dev
connection).

### API docs (`/docs`) supply chain

The Swagger UI page loads its CSS/JS from a pinned `swagger-ui-dist` version
with a Subresource Integrity hash — the browser refuses to run it if the CDN
ever serves something that doesn't match, so a compromised CDN edge or a
hijacked npm release can't silently inject JS into your docs page. `/docs` and
`/openapi.json` are also only served in `dev=True` by default in the first
place — see [Deployment](../deployment.md).

### Body-size limit

The app rejects request bodies over `max_body_size` (default 16 MB) with a
413, protecting against memory-exhaustion uploads.

!!! info "Malformed input fails clean, not loud"
    A non-UTF-8 form field, a malformed multipart boundary, or a pathologically
    deeply-nested JSON body all resolve to a clean `400 Bad Request` — found and
    locked in by fuzzing the parsers with `hypothesis` (see
    [Continuous scanning](#continuous-scanning)), not left to surface as an
    unhandled 500.

## The hardening toolkit — wire in what your deployment needs

None of these are on by default, because the framework can't know your
topology (do you have a reverse proxy? one caller or the public internet? is
Redis shared?). Each is a single line.

```python
from endocore.middleware import (
    security_headers_middleware, cors_middleware, rate_limit_middleware,
    proxy_headers_middleware, timeout_middleware, csrf_middleware,
    ip_allowlist_middleware,
)

middlewares = [
    security_headers_middleware(hsts=True),          # nosniff, DENY frames, HSTS
    cors_middleware(allow_origins=["https://app.example.com"]),
    ip_allowlist_middleware(allowed=["203.0.113.7"]),  # only if you have one known caller
    rate_limit_middleware(limit=100, window=60),
    proxy_headers_middleware(trusted=["10.0.0.1"]),  # trust X-Forwarded-* only from these
    timeout_middleware(seconds=30),
    csrf_middleware(secret="…"),
]
```

**IP allowlisting** — restrict a backend to one known caller (a frontend, an
internal network) by source IP/CIDR rather than trusting a header the caller
could just lie in:

```python
from endocore.middleware import ip_allowlist_middleware
middlewares = [ip_allowlist_middleware(allowed=["203.0.113.7", "10.0.0.0/24"])]
```

Put `proxy_headers_middleware` first if requests arrive through a reverse
proxy, or every request will carry the proxy's IP instead of the real client's.

**Cache signing** — `RedisCache` values are pickled; `pickle.loads()` on
whatever bytes Redis returns is only as safe as Redis itself. Pass `secret=`
to HMAC-sign each value (bound to its cache key, so a signed blob can't be
copied to a different key and still verify) and reject anything unsigned or
tampered as a cache miss instead of deserializing it:

```python
CacheExtension(backend="redis", secret=env("SECRET_KEY"))
```

Without `secret=`, values stay unsigned (as before) and a warning is raised.

## Know the limits — not bugs, but sharp edges

!!! warning "`timeout_middleware` doesn't stop sync handlers"
    Cancellation reaches an *async* handler's next `await` and actually stops
    it. A *sync* handler runs in a worker thread — Python can't forcibly kill
    a running thread, so it keeps running to completion in the shared thread
    pool even after the client gets its 504. Enough slow sync handlers can
    still exhaust that pool and stall unrelated requests despite every
    individual response looking fine. Bound the real work too (a DB statement
    timeout, an HTTP client timeout) — don't rely on this middleware alone for
    sync code.

!!! warning "Compression + secrets (BREACH)"
    `gzip_middleware` compresses any response over `minimum_size` with no idea
    what's in it. A response that embeds both a secret (a CSRF token, a
    session id) and attacker-influenced reflected input (an echoed query
    param) in the same body is a compression oracle regardless of what
    compresses it. Keep the two apart, or skip compression for pages that
    embed one.

## Application-level risks the framework can't decide for you

- **Mass assignment** — `Model(**body)` / `Model.objects.create(**body)` sets
  every key you pass it, including ones you didn't mean to expose (`is_staff`,
  `pk`, ...). The framework can't guess which fields a given endpoint should
  accept from the client; build the dict from named, explicit fields
  (`Model(name=body["name"])`) rather than splatting a request body directly,
  same as you would with any ORM.
- **Open redirect** — `Response.redirect(location)` sends exactly the
  `location` you give it. If it comes from request input (`?next=`), validate
  it's a same-site path before redirecting, unless an external redirect is
  actually the intended behavior (e.g. an OAuth callback).
- **Path params into file paths** — a captured segment (`[id]`) is just a
  URL-decoded string; the router validates nothing about its *content* (it
  only has to match a dynamic path segment). `open(f"uploads/{id}")` built
  from it directly is a path-traversal bug (`id="../../etc/passwd"`) like
  anywhere else user input reaches a filesystem call — use `FileField`'s
  storage, or validate against an allowlist/known ID space yourself.

## Continuous scanning

Every push and PR runs a dedicated `security` CI job alongside the test
matrix:

- **`bandit`** — static analysis over `endocore/`. Every existing finding is
  either the HMAC-signed cache pickle path or the ORM's SQL-building layer
  (identifiers quoted, values always bound — annotated `# nosec` line by line
  with the reason, not a blanket suppression); a *new* raw-SQL or pickle
  pattern anywhere else still fails the build.
- **`pip-audit`** — checks EndoCore's actual dependency tree (frozen right
  after install, before the scanners themselves are added to the same
  environment) against known CVEs.

The parsers (`multipart`, JSON body, query string) are additionally
property-fuzzed with `hypothesis` as part of the audit that produced this
page — every crash it found was fixed and locked in with a regression test.

## Production checklist

- [ ] Set a strong secret for signed cookies / CSRF (from env, not in code).
- [ ] `configure_storage(key=…)` from a secret manager; back the key up.
- [ ] Enable `security_headers_middleware(hsts=True)` behind TLS.
- [ ] Restrict `cors_middleware(allow_origins=[…])` to your front-ends.
- [ ] Set `ws_allowed_origins=[…]` if any websocket endpoint reads the session.
- [ ] Put `proxy_headers_middleware(trusted=[…])` if behind a load balancer.
- [ ] Add `ip_allowlist_middleware` if only one caller should ever reach this API.
- [ ] Add `rate_limit_middleware` (or a Redis-backed limiter) on public routes.
- [ ] Pass `secret=` to `CacheExtension(backend="redis", ...)` if that Redis
      instance isn't fully trusted.
- [ ] Run over HTTPS; terminate TLS at your proxy.
