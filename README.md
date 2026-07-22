# EndoCore

<p>
  <a href="https://pypi.org/project/endocore/"><img alt="PyPI" src="https://img.shields.io/pypi/v/endocore.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue.svg">
  <img alt="Tests" src="https://img.shields.io/badge/tests-1679%20passing-brightgreen.svg">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green.svg">
  <a href="https://discord.gg/jwvGj2M9EX"><img alt="Discord" src="https://img.shields.io/badge/chat-discord-5865F2?logo=discord&logoColor=white"></a>
</p>

### Your folder tree *is* your API. No routers. No decorators. No drift.

```
Api/v1/User/[id]/Get.py    ->  GET  /v1/user/42        (id="42")
Api/v1/User/Role/Post.py   ->  POST /v1/user/role
Api/v2/User/[id]/Get.py    ->  GET  /v2/user/42         (v1 keeps working, untouched)
```

Drop a file in the right folder. The endpoint exists — routed, versioned, and
showing up in `end routes` and `/docs` — with zero registration code. Delete
the file, the endpoint is gone. Routes are discovered directly from the
project structure, so there's no separate router table that can drift from
what the code actually does.

```python
# Api/v1/User/Role/Post.py  ->  POST /v1/user/role
from endocore import Request, Response

async def handler(request: Request) -> Response:
    data = await request.json()
    return Response.json({"created": data["name"]}, status=201)
```

That's a real, complete, working endpoint. No `app = FastAPI()`, no
`@app.post(...)`, no import to wire up anywhere. **The file's path and name
are the whole contract.**

📖 **Full documentation:** https://endocore.readthedocs.io (EN / RU) — every
guide below goes into far more depth than this README.
💬 **Community:** https://discord.gg/jwvGj2M9EX — questions, showcase, help.

---

## The problem this solves

Every growing API codebase eventually drifts: the route table says one thing,
the handler code says another, and "which version does this endpoint belong
to?" becomes an archaeology exercise. Decorator-based routers make this worse
as they scale — the routes live in your head, scattered across files that
import each other in whatever order someone wrote them.

EndoCore eliminates that entire class of drift. The `Api/` directory *is* the
route table. `end routes` doesn't introspect decorators or import your whole
app to find them — it just reads the tree, because the tree already is the
answer. A new API version (`v2`) is `shutil.copytree` with a filter, so `v1`
shares no router state with it and can't be touched by a `v2` change — no
`if version == 2` branches rotting in a handler, no versioning that only
works if everyone remembers the convention.

```text
Application
  → Router (reads Api/ — no decorators, no import-time registration)
    → Middleware chain (logging, CORS, auth, ...)
      → Dependency injection (Depends(), providers, path params)
        → Your handler
          → ORM (optional) → SQLite / PostgreSQL
```

## 60 seconds to a running API

```bash
pip install endocore
end new myapp && cd myapp
end dev                       # http://127.0.0.1:8000/docs
```

`end new` scaffolds a runnable app (`Api/`, `Models/`, `Services/`,
`Middleware/`). `end dev` boots it with the file watcher on — edit a handler,
save, the route table reloads in-process (no restart). Open `/docs` for a
live Swagger UI generated from your actual endpoints.

## What you get, out of the box

One `pip install`, one process, no assembly required:

| | |
|---|---|
| **Routing & versioning** | folder tree = routes; `vN` folders coexist forever |
| **ORM** | SQLite + PostgreSQL, sync *and* async, connection pooling, migrations with rollback |
| **Security** | parameterized SQL only, quoted/validated identifiers, scrypt password hashing, signed sessions, CSRF, rate limiting |
| **Real-time** | file-based WebSockets (`Socket.py`) + pub/sub rooms |
| **DI** | `Depends(...)`, FastAPI-style, nested, per-request cached |
| **Validation** | optional pydantic — a typed param is validated from the body, 422 on failure |
| **Ops** | structured logging with secret masking, `/openapi.json` + Swagger UI, cache (memory/Redis), background tasks |
| **Integrations** | Redis, Celery, SMTP email — plug in via `extensions.py` |
| **CLI** | `end create`, `end dev`, `end version create`, `end makemigrations`, `end routes`, `end check`, `end doctor` |

**Exactly one required dependency:** `uvicorn`. The resolver, loader,
Request/Response, middleware chain, ORM and CLI are all standard library —
nothing else is on the critical path of "does this framework start."

## Proof, not promises

- **1679 tests** in the framework's own suite (routing matrices, ORM dialect
  parity, SQL-injection tests, migration rollback, DI edge cases).
- **Three full demo apps** in [`demos/`](demos/) that don't just run — they're
  **race-tested under real concurrency**: a kanban board with live WebSocket
  updates, a room-booking system where 8 simultaneous requests for the same
  slot produce exactly one winner, and a shop with idempotent purchases +
  payment-webhook handling that survives being retried mid-flight or hit by
  6 concurrent duplicate requests without double-charging anyone.
- **A connection pool test suite that runs against real PostgreSQL**
  (`tests/orm/test_postgres_pool.py`), proving transaction isolation under
  concurrency before you'd trust it in production — not just on SQLite.

## A quick look at the ORM

```python
from endocore.orm import Model, fields, configure, create_all, Q, F

class User(Model):
    name   = fields.CharField(max_length=100)
    age    = fields.IntegerField(default=0)
    active = fields.BooleanField(default=True)

configure(backend="sqlite", database="app.db")   # or backend="postgres", pool_size=10, ...
create_all(User)

User.objects.create(name="Ada", age=36)
User.objects.filter(age__gte=18).order_by("-age")             # lazy QuerySet
User.objects.filter(Q(age__lt=18) | Q(name__icontains="a"))   # Q objects
User.objects.filter(age__gte=18).update(active=True)          # bulk update
User.objects.filter(pk=1).update(age=F("age") + 1)            # atomic F() expression

# non-blocking, for ASGI handlers:
user = await User.objects.aget(pk=1)
async with endocore.orm.aatomic():
    await user.asave()
```

Every value is bound through the driver (never string-formatted into SQL),
every identifier is validated and quoted, only a fixed whitelist of lookups
produces SQL, and `LIMIT`/`OFFSET` are coerced to `int`. This isn't a layer you
opt into — it's the only way the ORM knows how to build a query.

**→ Full ORM reference:** [docs/orm/](https://endocore.readthedocs.io/en/latest/orm/) —
fields, relations, aggregates, transactions, migrations, encrypted files.

## How it compares

| | EndoCore | FastAPI | Django |
|---|---|---|---|
| Routing | file path = route | decorators | decorators (`urls.py`) |
| Versioning | `vN` folders, built in | manual | manual (separate apps) |
| ORM | built in (sync + async) | none (bring your own) | built in (sync) |
| Migrations | built in, with rollback | Alembic (separate) | built in |
| Core dependencies | 1 (`uvicorn`) | Starlette + pydantic | none (own stack) |
| Codebase size | small enough to read in an afternoon | large | very large |

**→ Full comparison with trade-offs:** [docs/comparison.md](https://endocore.readthedocs.io/en/latest/comparison/)

### Coming from FastAPI?

The mental model carries over directly — same ASGI deployment, a similar
`Request`/`Response` shape, the same `Depends(...)` pattern. What changes is
where a route *lives*: instead of a decorator wherever you happened to put
it, `POST /v1/user/role` is the file `Api/v1/User/Role/Post.py`. You can
migrate incrementally, endpoint by endpoint, since nothing about one route's
file has anything to do with another's.

## Everything else is one link away

The docs cover every corner in depth — routing rules and edge cases,
dependency injection resolution order, middleware ordering, every ORM field
and lookup, transactions and connection pooling, migrations, WebSockets and
pub/sub, caching, service integrations, security hardening, deployment, and a
full step-by-step tutorial:

📖 **https://endocore.readthedocs.io** (English / Russian, kept in sync)

```bash
py -3 -m pip install -e ".[dev]"      # clone + install for local development
pytest -q                              # the framework's own test suite
cd example && end dev                  # run the bundled example app
```

Run the framework's own tests with `pytest`; run an app's tests with `end test`.

---

EndoCore is built around one idea: **your directory tree should already
describe your API.** No duplicated routing tables, no hidden registration,
no drift between what the code does and what the docs say it does — just
files, folders, and behavior you can predict by looking at where things live.

## License

MIT. See [`LICENSE`](LICENSE). Contributions: [`docs/contributing.md`](docs/contributing.md).
Changelog: [`CHANGELOG.md`](CHANGELOG.md).

> Personal / sporting-interest project, Beta (`0.7.0b2`). Client-usable today;
> stabilizing toward `1.0`.
