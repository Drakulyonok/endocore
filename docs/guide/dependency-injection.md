# Dependency Injection

Dependency injection (DI) is how a handler gets ready-made objects — a database
pool, settings, the current user — without creating them in every file. You add
a parameter to the handler, EndoCore fills it in. It works like FastAPI's:
`Depends(...)` plus app-level providers — same idea, small implementation
(`endocore/core/di.py`, no separate DI framework underneath).

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

Dependencies can depend on other dependencies (nested, to any depth), and are
**cached per request** — a dependency used twice in the same request's
resolution tree runs once. The cache key is the dependency **function object
itself**: two different `Depends(db)` markers pointing at the *same* `db`
function share one cached result; `Depends(db)` and `Depends(other_db)` never
do, even if `other_db` happens to return an identical-looking object.

## How a handler is dispatched at all

Before any of this runs, the dispatcher checks whether your handler is the
*simplest possible shape*: exactly one parameter, named `request`, with no
default value. If so, it skips the whole DI machinery below and calls
`handler(request)` directly — this "trivial handler" fast path exists purely
for the common case's sake, and its check result is cached per-function, so
it costs nothing on repeat calls. The moment you add a second parameter, a
default, or `Depends(...)`, the handler goes through full resolution instead.

## Resolution order — precisely

For **each** handler parameter, in this exact order (this is the literal
control flow of `di._resolve`, not a paraphrase — the order matters, because
more than one rule can technically apply to the same parameter):

1. **The parameter's default is `Depends(fn)`** → resolve `fn` (recursively,
   through the same rules) and cache the result. This is checked **before**
   anything else — including before the `request`/`websocket` special-casing
   below. In practice this never collides (nobody writes
   `request = Depends(...)`), but it's worth knowing which rule actually wins
   if you ever do something unusual.
2. **The parameter is named `request`, or annotated `Request`** → the current
   `Request` (or `None` inside a WebSocket handler — see below).
3. **The parameter is named `websocket`, or annotated `WebSocket`** → the
   current `WebSocket` (or `None` inside an HTTP handler).
4. **The name matches a captured path param** (`[id]` → a parameter literally
   named `id`) → that string value. This works for both HTTP and WebSocket
   handlers — whichever of `request`/`websocket` is active supplies
   `path_params`.
5. **An app-level provider matches** — checked by **annotation (type) first**,
   then by **parameter name** if no type match exists. See below.
6. **The annotation is a pydantic `BaseModel` subclass** → validated from the
   JSON request body. **HTTP only** — this rule is skipped entirely for
   WebSocket handlers (there's no request body to validate against), so a
   `BaseModel`-annotated parameter on a `Socket.py` handler falls through to
   the next rule instead.
7. **The parameter has its own plain default value** (not `Depends(...)`) →
   used as-is.
8. **None of the above matched** → `DIError` is raised, naming the parameter
   and the function — this is a boot-time-adjacent failure in practice, since
   handlers are imported eagerly; a genuinely unresolvable parameter usually
   surfaces the first time the route is *hit*, not at import time (DI runs
   per-request, not at import), so cover new handlers with at least one test
   request rather than trusting `endo check` alone to catch this class of bug.

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

Providers are **singletons by default**: the *factory function itself* is
the cache key (`app._singletons[factory]`), built once on first use and
reused for the life of the process — not per-request like `Depends(...)`
results. The `providers.py` dict form is always singleton (there's no
per-entry option there); for a factory that should run fresh on every
resolution, register it at runtime instead —
`app.provide("db", make_pool, singleton=False)`, e.g. from `hooks.py` or an
extension's `setup(app)`. A provider factory can itself take
parameters resolved through the same DI rules (including `Depends(...)` and
other providers) — providers and `Depends` share one resolver, they're not
two separate systems.

If a provider is registered under **both** a name and a type that could
apply to the same parameter (unusual, but possible), **type wins** — that's
rule 5 above, and it's a property of `ProviderRegistry.get()`, not of
declaration order in `providers.py`.

## Pydantic bodies

With `endocore[pydantic]` installed, a parameter annotated with a `BaseModel`
is validated from the JSON body — **422** with per-field errors on failure,
and its schema shows up in `/docs`:

```python
from pydantic import BaseModel

class UserIn(BaseModel):
    name: str
    age: int

async def handler(request, data: UserIn):    # POST body -> validated UserIn
    return Response.json({"name": data.name}, status=201)
```

Both pydantic v1 (`.parse_obj`) and v2 (`.model_validate`) are supported —
whichever is installed is detected automatically, no configuration needed.
A validation failure raises `UnprocessableEntity` (422) with `detail` set to
a list of `{"field": "age", "message": "..."}` entries, one per failing
field — the same shape [Exceptions](exceptions.md) documents for every other
HTTP error, so a client-side error handler doesn't need a special case for
body-validation failures specifically.

## Performance

Signatures and resolved type hints are cached per function (`inspect.signature`
and `typing.get_type_hints` are not cheap to call on every request), and the
"is this a trivial handler" check above is a cached boolean too. In practice
DI adds negligible overhead even for handlers with several nested
dependencies — the cost that matters is whatever your dependency functions
actually *do* (a DB query, an HTTP call), not the resolution machinery
around them.
