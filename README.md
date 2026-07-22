# EndoCore

<p>
  <a href="https://pypi.org/project/endocore/"><img alt="PyPI" src="https://img.shields.io/pypi/v/endocore.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue.svg">
  <img alt="Tests" src="https://img.shields.io/badge/tests-1679%20passing-brightgreen.svg">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green.svg">
</p>

📖 **Documentation:** https://endocore.readthedocs.io (EN / RU) · see [`HOSTING.md`](HOSTING.md) to deploy it free.

**Status: Beta (0.7.0b1) — client-usable.** · Python ≥ 3.11 · core dependency (`uvicorn`) · optional `psycopg`, `cryptography`, `redis`, `celery`, `pydantic` · **1679 tests**

Async-capable ORM (connection pooling, `aatomic()`) · sessions & scrypt auth · WebSockets + pub/sub · cache · OpenAPI/Swagger · pydantic bodies · Redis/Celery/Email integrations · migrations with rollback, alter & rename.

**File-based ASGI backend framework — the folder tree *is* the API — with a small, secure ORM.**

No manual routers, no registration decorators, no config. Drop a file in the
right folder and the endpoint exists. Routing, versioning and the CLI are all
just **operations over one directory tree**.

> Personal / sporting-interest project. Core has exactly one external
> dependency: `uvicorn`. Everything that makes up the idea (resolver, loader,
> Request/Response, middleware, CLI) is written from the standard library.

---

## Conventions

| Rule | Meaning |
|------|---------|
| `FILE = ROUTE`   | one handler file = one endpoint |
| `FOLDER = URL segment` | `Api/User/Role/` → `/user/role` |
| `FILE NAME = HTTP method` | `Post.py`, `Get.py`, `Patch.py`, `Delete.py` (normalized via `.upper()`) |
| `[id] = dynamic segment` | `Api/User/[id]/` matches `/user/42`, captures `id=42` |
| `vN = version` | first path segment matching `^v\d+$` |

Layers are strict: **API** files are thin (parse → call service → respond),
**Services** hold business logic, **Models** describe data, **Middleware** wraps
requests, **Utils** are pure functions. Thin endpoints are a *requirement* of
versioning: fat endpoints turn every new version into copy-pasted logic.

---

## Architecture

```
endocore/                    # THE FRAMEWORK (installable package, `end` CLI)
  core/
    discovery.py             # scan Api/ tree -> RouteSpec list  (the one tree-walk)
    router.py                # path -> Route resolution rules (version, [id], method)
    registry.py              # route tree + resolver (cached at boot)
    loader.py                # importlib dynamic import of handlers (error-resilient)
    request.py               # Request over the ASGI scope
    response.py              # Response -> ASGI send messages
    middleware.py            # middleware chain (onion / call_next)
    logging.py               # stdlib logging wrapper + sensitive-data masking
    application.py           # async def app(scope, receive, send)
    exceptions.py            # framework errors
  middleware/
    logging.py               # request logging middleware (timing + masking)
  cli/
    main.py                  # argparse entry point `end`
    templates.py             # scaffolding file bodies
    commands/                # create / dev / version / test
  asgi.py                    # create_app() factory for uvicorn
  orm/                       # small secure ORM (SQLite + PostgreSQL)
    backends/                # base (security-critical) + sqlite + postgres dialects
    fields.py  model.py      # declarative models + metaclass
    query.py   compiler.py   # QuerySet, Q objects, parameterized SQL compiler
    connection.py  schema.py # connections/transactions + create_table

example/                     # a demo application served by `end`
  Api/                       # file-based routes (folder = segment, file = method)
  Services/                  # GLOBAL services (shared across all versions)
  Models/  Middleware/  Utils/
  Tests/                     # user-written tests (framework never generates these)
```

The **application** you build lives next to `Api/` (see `example/`). The
**framework** you install is `endocore`.

---

## CLI

```
end create user/role post      # scaffold POST endpoint + structure
end create v2/user/role        # scaffold into an explicit version
end dev                        # run server + file watcher
end version create 2           # copy latest version (endpoints + LOCAL services) -> v2
end version list               # list existing versions
end test                       # run user tests (optional)
```

`end version create` is `shutil.copytree` with a filter — versioning is a
special case of routing, not a separate subsystem. Global `Services/` are shared
and never copied; local `Api/vN/.../Services/` are versioned and copied.

---

## Versioning

A version applies to the **whole endpoint with all its methods**. `v1` and `v2`
coexist so old clients never break. After `v2` is created, `v1` behaves
identically to before — if a v2 change could touch v1, the versioning is fake.

A request without a version prefix (`POST /user/role`) → **404** (explicit is
better than implicit; default-to-latest is deliberately out of MVP scope).

---

## Logging

A wrapper over stdlib `logging` + middleware that measures time and **masks
sensitive keys** (`password`, `token`, `authorization`, `secret`, …) *before*
writing — the log middleware sees the raw inbound JSON, so masking must live at
the logger layer.

```
[INFO]  POST /v2/user/role 12ms
[ERROR] validation failed in RoleService
```

---

## Writing an app

**A handler file** defines one `handler` (sync or async); an optional `init()`
runs once at boot:

```python
# Api/v1/User/Role/Post.py  ->  POST /v1/user/role
from endocore import Request, Response, HTTPError

async def handler(request: Request) -> Response:
    data = await request.json()
    if not data:
        raise HTTPError(422, "body required")   # short-circuit with a status
    return Response.json({"ok": True}, status=201)
```

A handler may return a `Response`, a `dict`/`list` (JSON 200), a `str` (text),
`None` (204), or `(content, status[, headers])`.

**Registering middleware** — list it, ordered, in `Middleware/__init__.py`:

```python
# Middleware/__init__.py
from Middleware.auth import auth_middleware
middlewares = [auth_middleware]   # first = outermost (inside framework logging)
```

Each middleware is `async def mw(request, call_next) -> Response`: return an
early `Response` to short-circuit, or `await call_next(request)` to pass inward.

## ORM (SQLite & PostgreSQL)

A small Django-flavoured ORM. **Security is the point:** every value is bound by
the driver (never string-formatted into SQL), identifiers are validated and
quoted, only whitelisted lookups produce SQL, LIKE wildcards in user input are
escaped, and `LIMIT`/`OFFSET` are coerced to integers.

```python
from endocore.orm import Model, fields, configure, create_all, Q

class User(Model):
    name   = fields.CharField(max_length=100)
    age    = fields.IntegerField(default=0)
    active = fields.BooleanField(default=True)

configure(backend="sqlite", database="app.db")     # or backend="postgres", host=..., dbname=...
create_all(User)

User.objects.create(name="Ada", age=36)
User.objects.filter(age__gte=18).order_by("-age")           # QuerySet, lazy
User.objects.filter(Q(age__lt=18) | Q(name__icontains="a")) # Q objects
User.objects.get(name="Ada")                                # -> instance / DoesNotExist
User.objects.filter(active=True).update(age=0)              # bulk update
User.objects.values_list("name", flat=True)                # projections
```

Lookups: `exact iexact contains icontains startswith endswith gt gte lt lte in
isnull range`. Fields include ints (incl. Small/Positive), `Float`, `Decimal`,
`Char`/`Text`/`Slug`/`Email`/`URL`/`GenericIPAddress`, `UUID`, `JSON`, `Binary`,
`Date`/`DateTime`/`Time`/`Duration`, `ForeignKey`, and an encrypted `FileField`.
Transactions via `with endocore.orm.atomic():`.

**Relations & expressions** (Django-level):

```python
Person.objects.filter(city__country__name="France")     # cross-table (JOIN)
Person.objects.select_related("city__country")           # fetch related in one query
Post.objects.update(views=F("views") + 1)                # F expressions
Post.objects.aggregate(total=Sum("views"), n=Count("*")) # aggregates
Row.objects.distinct(); Row.objects.get_or_create(...)   # + earliest/latest/bulk_create
```

**Encrypted files** — stored in any folder, **encrypted at rest** (AES-256-GCM):
if the storage leaks, files are unrecoverable without the separate key.

```python
from endocore.orm import configure_storage, generate_key

configure_storage(root="/var/data/uploads", key=generate_key())  # key -> keep it safe

class Doc(Model):
    file = fields.FileField(upload_to="docs")

d = Doc.objects.create(file=b"...bytes...")   # written encrypted; DB stores only a key
d.file.read()                                 # decrypts on demand

PostgreSQL needs the driver: `pip install "endocore[postgres]"`; encrypted files:
`pip install "endocore[files]"`.

## Batteries

**Dependency injection** — declare it, get it (nested, per-request cached):

```python
from endocore import Request, Response, Depends

def db(): ...
async def handler(request: Request, conn = Depends(db)):
    return Response.json({"ok": True})
```
App-level providers live in `providers.py` (`providers = {"db": make_pool}`).

**Config** — typed, env-backed `Settings` (`from endocore import Settings, env`).
**Exceptions** — `raise NotFound()`, `Unauthorized`, `Forbidden`, `Conflict`,
`UnprocessableEntity`, `TooManyRequests`, … (rendered to their status).
**Cookies** — `response.set_cookie(...)`, signed cookies, `request.cookies`.
**Forms/uploads** — `await request.form()`, `await request.files()`.
**Lifecycle** — `hooks.py` (`on_startup` / `on_shutdown`) + response background tasks.

**Middleware** (`from endocore.middleware import ...`, list them in
`Middleware/__init__.py`): `cors_middleware`, `security_headers_middleware`,
`gzip_middleware`, `proxy_headers_middleware`, `rate_limit_middleware`,
`timeout_middleware`, `csrf_middleware`.

**Migrations** with rollback:

```bash
end makemigrations initial
end migrate
end rollback            # undo the last migration
```

Other CLI: `end new <Name>`, `end routes`, `end check`, `end doctor`, `end openapi`.

## Real-time, cache & integrations

**WebSockets** — a file named `Socket.py` in the Api tree:

```python
# Api/v1/Chat/Socket.py  ->  ws /v1/chat
async def handler(websocket):
    await websocket.accept()
    async for message in websocket.iter_text():
        await websocket.send_text(f"echo: {message}")
```

**Cache** — `from endocore import get_cache, cached`:

```python
get_cache().set("k", {"v": 1}, ttl=60)

@cached(ttl=30)
async def expensive(x): ...
```

**OpenAPI** — served at `/openapi.json` and Swagger UI at `/docs` (also `end openapi`).

**Service integrations** — list them in `extensions.py`; they register DI
providers and hook the lifespan:

```python
# extensions.py
from endocore.extensions import RedisExtension, CacheExtension, EmailExtension
extensions = [
    RedisExtension(url="redis://localhost:6379/0"),
    CacheExtension(backend="redis"),
    EmailExtension(host="smtp.example.com", port=587, use_tls=True),
]
```
Ship your own by subclassing `Extension`. Optional deps: `endocore[redis]`,
`endocore[celery]`.

## ORM relations & aggregates

```python
author.book_set.all()                                  # reverse FK
Author.objects.annotate(n=Count("books"))              # aggregate over a relation
Book.objects.only("title"); Book.objects.defer("body") # partial fetch
Book.objects.bulk_update(books, ["price"])             # batch write
```

## Async ORM (non-blocking for ASGI)

The sync ORM runs in a threadpool, so handlers stay non-blocking:

```python
user = await User.objects.aget(id=1)
await User.objects.acreate(name="Ada")
async for u in User.objects.filter(active=True):
    ...
await user.asave()
```

## WebSocket pub/sub

```python
from endocore import WebSocketManager
chat = WebSocketManager()

async def handler(websocket):               # Api/v1/Chat/Socket.py
    await chat.connect(websocket, room="lobby")
    try:
        async for msg in websocket.iter_text():
            await chat.broadcast(msg, room="lobby")
    finally:
        chat.disconnect(websocket)
```

## Typed bodies (pydantic, optional)

A handler param typed as a pydantic model is validated from the JSON body
(422 on error) and documented in `/docs`:

```python
from pydantic import BaseModel
class UserIn(BaseModel):
    name: str
    age: int

async def handler(request, data: UserIn):   # POST body -> validated UserIn
    return Response.json({"name": data.name}, status=201)
```

## Getting started

```bash
py -3 -m pip install -e .
cd example
end dev                 # http://127.0.0.1:8000
# GET /v1/user/role, GET /v1/user/42, POST /v1/user/role, GET /v1/user/0 -> 404
# GET /v1/post, POST /v1/post {"title": "..."}   (ORM-backed)
```

Run the framework's own tests with `pytest`; run an app's tests with `end test`.

## Demos

Three end-to-end apps under [`demos/`](demos/) exercise the framework the way a
real backend would — including the concurrency edge cases:

- **[teamboard](demos/teamboard/)** — kanban boards with live WebSocket updates.
- **[booking](demos/booking/)** — slot booking; race-tested for no double-booking.
- **[shop](demos/shop/)** — idempotent purchases + payment-gateway webhook,
  race-tested for no-overdraft spends (SQLite by default, PostgreSQL pool on request).

Each has its own `README.md`, `end dev`, and `pytest Tests`.
