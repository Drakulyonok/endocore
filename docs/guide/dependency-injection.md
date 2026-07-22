# Dependency Injection

Dependency injection (DI) is how a handler gets ready-made objects — a database
pool, settings, the current user — without creating them in every file. You add
a parameter to the handler, EndoCore fills it in.

It works like FastAPI's: `Depends(...)` plus app-level providers.

## `Depends`

```python
from endocore import Request, Response, Depends

async def db():
    return get_pool()                     # a dependency (sync or async)

async def current_user(request: Request, pool = Depends(db)):
    token = request.headers.get("authorization")
    return await pool.user_from(token)

async def handler(request: Request, user = Depends(current_user)):
    return Response.json({"user": user})
```

Dependencies can depend on other dependencies (nested), and are **cached
per-request** — a dependency used twice runs once.

## Resolution order

For each handler parameter, in order:

1. `request` (by name or `Request` annotation) → the Request.
2. `websocket` (by name or `WebSocket` annotation) → the WebSocket.
3. Default is `Depends(fn)` → resolve `fn`.
4. Name matches a captured **path param** (`[id]`) → that value.
5. An app-level **provider** for the annotation (type) or name.
6. A **pydantic model** annotation → validated from the JSON body (see below).
7. The parameter's own default, if any.
8. Otherwise → `DIError`.

## App-level providers

Register singletons/services once; inject them by **name** or **type**:

```python
# providers.py
from Services.db import make_pool
from Services.settings import Settings, get_settings

providers = {
    "db": make_pool,          # inject a param named `db`
    Settings: get_settings,   # inject a param annotated `Settings`
}
```

```python
async def handler(request, db, settings: Settings):
    ...
```

Providers are **singletons by default** (built once, reused). You can also
register at runtime: `app.provide("db", make_pool, singleton=True)`.

## Pydantic bodies

With `endocore[pydantic]`, a parameter annotated with a `BaseModel` is validated
from the JSON body — **422** with field errors on failure, and its schema shows
up in `/docs`:

```python
from pydantic import BaseModel

class UserIn(BaseModel):
    name: str
    age: int

async def handler(request, data: UserIn):    # POST body -> validated UserIn
    return Response.json({"name": data.name}, status=201)
```

## Performance

The common `handler(request)` shape uses a **fast path** that skips resolution
entirely. Signatures and type hints are cached, so DI adds negligible overhead
for typical handlers.
