# EndoCore

**A file-based ASGI backend framework — the folder tree *is* the API.**

No routers, no decorators, no registration config. Drop a file in the right
folder and the endpoint exists. Routing, versioning and the CLI are all just
**operations over one directory tree**.

<p align="center">
  <em>Pure ASGI · one core dependency (<code>uvicorn</code>) · a secure ORM · DI ·
  WebSockets · cache · OpenAPI · migrations · 1600+ tests.</em>
</p>

<p align="center" markdown>
[Get started](getting-started/quickstart.md){ .md-button .md-button--primary }
[Tutorial](getting-started/tutorial.md){ .md-button }
[vs FastAPI](comparison.md){ .md-button }
[Discord](https://discord.gg/jwvGj2M9EX){ .md-button }
</p>

---

## The idea in ten seconds

```text
Api/
  v1/
    User/
      Role/
        Get.py      # GET  /v1/user/role
        Post.py     # POST /v1/user/role
      [id]/
        Get.py      # GET  /v1/user/42   ->  id = "42"
```

```python
# Api/v1/User/Role/Get.py
from endocore import Request, Response

async def handler(request: Request) -> Response:
    return Response.json({"roles": ["admin", "editor", "viewer"]})
```

```bash
endo dev            # http://127.0.0.1:8000
```

The folder is the URL, the file name is the HTTP method, `[id]` captures a
value, and the first `vN` folder is the API version. That's the entire routing
model.

---

## Why EndoCore

<div class="grid cards" markdown>

-   :material-file-tree: **File = route**

    Structure is the API. What you see in the tree is exactly what the server
    serves. No hidden registration, no drift between code and routes.

-   :material-database-lock: **Secure ORM (SQLite + PostgreSQL)**

    Django-flavoured, but security-first: every value is bound by the driver,
    identifiers are validated and quoted, lookups are whitelisted. Async-ready.

-   :material-needle: **Dependency Injection**

    FastAPI-style `Depends(...)` plus app-level providers — nested, cached
    per-request, resolved by type or name.

-   :material-lightning-bolt: **Batteries included**

    WebSockets + pub/sub, cache (memory/Redis), CORS/CSRF/gzip/rate-limit
    middleware, cookies, background tasks, migrations with rollback, OpenAPI.

</div>

---

## A taste of the ORM

```python
from endocore.orm import Model, fields, configure, create_all, Count

class Author(Model):
    name = fields.CharField(max_length=100)

class Book(Model):
    title  = fields.CharField(max_length=200)
    author = fields.ForeignKey(Author, related_name="books")
    tags   = fields.ManyToManyField("Tag")

configure(backend="sqlite", database="app.db")
create_all(Author, Book)

Author.objects.create(name="Ada")
Book.objects.filter(author__name="Ada")             # cross-table lookup (JOIN)
Author.objects.annotate(n=Count("books"))           # aggregate over a relation
await Book.objects.aget(id=1)                        # async (non-blocking)
```

---

## Install

```bash
pip install endocore
# extras: pip install "endocore[postgres,files,redis,pydantic]"
```

New here? Follow this path:

1. [Installation](getting-started/installation.md) — one `pip install`.
2. [Quickstart](getting-started/quickstart.md) — a working API in a minute.
3. [Tutorial](getting-started/tutorial.md) — a small blog API end-to-end:
   models, services, middleware, versions, tests.

---

## Status

EndoCore is in beta (`0.8.0b1`), stabilising toward `1.0`. It ships with 1600+
tests covering routing, the ORM (both dialects, injection tests), migrations,
middleware, DI, cache and WebSockets.

!!! note "One core dependency"
    The core depends on a single external package: `uvicorn`. The resolver,
    Request/Response, middleware, CLI and ORM are standard library. PostgreSQL,
    encrypted files, Redis, Celery and pydantic are optional extras. More in
    [Philosophy](getting-started/philosophy.md).
