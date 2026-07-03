# Architecture

EndoCore is a thin, legible pipeline. This page maps the whole system so you
always know where a request is and which module owns it.

## The two halves

```text
endocore/            ← the framework (installed package, the `end` CLI)
your_app/            ← your application (Api/, Services/, Models/, ...)
```

You import `endocore`; you *write* `your_app`. The framework never generates
your business logic — it discovers and serves it.

## Package layout

```text
endocore/
  core/
    discovery.py     # scan Api/ tree -> RouteSpec list  (the one tree-walk)
    router.py        # path parsing + matching rules (version, [id], method)
    registry.py      # route trie + resolver (built once at boot, cached)
    loader.py        # importlib dynamic import of handlers (error-resilient)
    request.py       # Request over the ASGI scope
    response.py      # Response / StreamingResponse -> ASGI send
    websocket.py     # WebSocket over the ASGI websocket scope
    middleware.py    # onion / call_next chain
    di.py            # Depends() + provider resolution
    application.py   # async def app(scope, receive, send) — ties it together
    cache.py  config.py  signing.py  pubsub.py  openapi.py  exceptions.py
  middleware/        # shipped middleware: logging, cors, csrf, gzip, ...
  orm/               # the ORM (models, fields, query, compiler, backends, ...)
  cli/               # the `end` CLI (create, dev, routes, migrate, ...)
  extensions/        # Redis, Celery, Email, Cache integrations
```

## Boot sequence

When the app starts, `Application.boot()`:

1. Puts the app directory on `sys.path` (so `from Services... import ...` works).
2. **Scans** `Api/` once with `pathlib.rglob("*.py")` → a list of `RouteSpec`.
3. **Imports** each handler with `importlib`, wrapped in `try/except`. One broken
   file is collected as a `BootError`, never fatal.
4. **Registers** handlers into a route **trie** (by version → segment).
5. Loads user middleware (`Middleware/__init__.py`), hooks (`hooks.py`),
   DI providers (`providers.py`), and extensions (`extensions.py`).
6. Builds the middleware pipeline once and logs a boot summary
   (`loaded N routes, M files with errors`).

The route tree is **cached**. In dev, a `watchfiles` watcher rebuilds it
in-process on change — no restart.

## Request flow

```text
                ┌─────────────────── middleware chain (onion) ───────────────────┐
scope/receive → │ logging → [ your middleware... ] → dispatch → handler → Response│ → send
                └────────────────────────────────────────────────────────────────┘
```

1. `Application.__call__` receives the raw ASGI `(scope, receive, send)`.
2. For `http`, it builds a `Request` and runs it through the **pipeline**.
3. The innermost layer, `_dispatch`, resolves the route in the trie, injects
   dependencies (`di.solve`), calls your `handler`, and coerces the return value
   into a `Response`.
4. The `Response` writes itself to `send`.

`websocket` scopes are handled by `_handle_websocket`; `lifespan` runs
startup/shutdown hooks and the dev watcher.

## The resolver (the heart)

Given `POST /v2/user/42/role`, the resolver:

- splits the path into segments;
- checks the first segment against `^v\d+$` → the **version**;
- walks the trie, preferring **static** children over the **dynamic** (`[id]`)
  child, capturing path params;
- looks up the **method** (`POST`) at the matched node.

Outcomes: `200` (matched), `404` (no such path/version), `405` (path exists,
wrong method). No version prefix → `404` by default (opt-in "latest" alias).

## Layers in your app

| Layer | Role |
|-------|------|
| **API** (`Api/`) | endpoint files — thin: parse → call service → respond |
| **Services** | all business logic; heavy code lives here |
| **Models** | data description (ORM models) |
| **Middleware** | request wrapping (auth, logging, CORS, ...) |
| **Utils** | pure functions, no side effects |

This separation is what makes versioning cheap: a new version copies thin
endpoints and *local* services, while global `/Services/` stay shared.
