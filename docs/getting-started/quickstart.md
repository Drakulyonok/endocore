# Quickstart

Build a running API in about a minute. No config files and no route
registration — you create folders and files, EndoCore serves them. This page
walks through exactly what each step produces and why, including the couple
of things that trip people up the first time (they're called out explicitly
below, not left for you to discover).

## 1. Scaffold a project

```bash
pip install "endocore[watch]"    # [watch] enables the dev-server auto-reload — see step 2
endo new blog
cd blog
```

!!! note "PowerShell"
    In PowerShell type `endo` instead of `endo` (`endo new blog`) — `endo` is a
    reserved word there (it's a PowerShell block keyword). Same CLI, different
    name; every other command below works identically with either.

`endo new blog` writes exactly this, nothing more (this is `endocore/cli/commands/new.py`,
not a guess):

```text
blog/
  Api/
    v1/
      Health/
        Get.py          # GET /v1/health — a liveness probe, so `endo dev` has
                         # something to serve immediately
  Middleware/
    __init__.py         # an empty `middlewares = [...]` list, commented examples
  Services/  Models/  Utils/  Tests/    # empty except a .gitkeep each
  hooks.py              # `on_startup` / `on_shutdown` lists, both empty stubs
  README.md
```

There is **no** `extensions.py` yet — that file is optional and only matters
once you actually wire up a service integration (Redis, Celery, email); see
[Extensions](../extensions/index.md). Don't create it speculatively.

## 2. Run the dev server

```bash
endo dev
```

You should see something like:

```text
[INFO] EndoCore booted: loaded 1 route, 0 middleware, 0 files with errors
[INFO] dev watcher on: .../blog/Api
[INFO] Uvicorn running on http://127.0.0.1:8000
```

Visit `http://127.0.0.1:8000/v1/health` — you'll get `{"status": "ok"}`.
Open `http://127.0.0.1:8000/docs` for the interactive **Swagger UI**, where you
can try every endpoint from the browser. (`/docs` is on automatically here
because `endo dev` runs with `dev=True` — in a production deployment it's off
by default; see [Configuration](../guide/configuration.md).)

!!! warning "No `dev watcher on: ...` line? Reload won't happen"
    The in-process file watcher needs the optional `watchfiles` package —
    that's what `pip install "endocore[watch]"` in step 1 was for. Without it,
    `endo dev` still runs the app perfectly normally, it just logs `dev watcher
    disabled (install 'watchfiles' for auto-reload)` instead, and every save
    in steps 3–6 below will need a manual restart (`Ctrl+C`, `endo dev` again)
    to take effect. If you skipped the `[watch]` extra, install it now:
    `pip install watchfiles`.

## 3. Add an endpoint

Either scaffold it:

```bash
endo create user/profile get
# -> Api/v1/User/Profile/Get.py   (GET /v1/user/profile)
```

`endo create` PascalCases each path segment for you (`user` → `User`) and
writes a minimal handler body; it targets the **latest existing version**
when you don't specify one (here, `v1`, since it's the only one). Run it
again with the same arguments and it won't clobber your edits — it prints
`exists: ...` and leaves the file alone.

…or just create the file yourself — `endo create` is a convenience, not a
requirement. **The folder is the path, the file name is the method**, full
stop:

```python
# Api/v1/User/Profile/Get.py
from endocore import Request, Response

async def handler(request: Request) -> Response:
    return Response.json({"name": "Ada", "role": "admin"})
```

Save the file — with the watcher running, EndoCore rescans `Api/` and
re-imports the changed handler in-process (no server restart, no dropped
connections). Open `http://127.0.0.1:8000/v1/user/profile` and the endpoint
is live. See [Routing](../guide/routing.md) for the full rule set, including
several edge cases worth knowing before your tree grows past a handful of
files.

## 4. Dynamic segments

A folder named `[id]` captures a path parameter, verbatim (not lower-cased,
unlike ordinary folder names — see [Routing](../guide/routing.md#dynamic-segments)):

```python
# Api/v1/User/[id]/Get.py
from endocore import Request, Response

async def handler(request: Request) -> Response:
    user_id = request.path_params["id"]         # "42" for /v1/user/42 — always a str
    return Response.json({"id": user_id})
```

`request.path_params["id"]` is always a `str` — EndoCore never guesses that
`"42"` should become the `int` `42`. Cast it yourself
(`int(request.path_params["id"])`) if your handler needs a number; an
invalid cast is your code's problem to handle (e.g. `raise
HTTPError(422, "id must be numeric")` around it), not the router's.

## 5. Read input

```python
# Api/v1/User/Post.py   (POST /v1/user)
from endocore import Request, Response, HTTPError

async def handler(request: Request) -> Response:
    data = await request.json()
    if not data.get("name"):
        raise HTTPError(422, "name is required")
    return Response.json({"created": data["name"]}, status=201)
```

`await request.json()` returns `None` for an empty body (not an error) and
raises `BadRequest` (→ 400) for a body that isn't valid JSON — so
`data.get("name")` above would raise `AttributeError` on `None` if the
client sent no body at all; guard for that explicitly
(`data = await request.json() or {}`) unless an empty body should genuinely
be a 500. `request` also gives you `request.query` (parsed query string),
`request.headers`, `request.cookies`, and `await request.form()` /
`await request.files()` for multipart uploads — see
[Request & Response](../guide/request-response.md).

## 6. Add the ORM

```python
# Models/blog.py
from endocore.orm import Model, fields, configure, create_all

configure(backend="sqlite", database="blog.db")

class Post(Model):
    title = fields.CharField(max_length=200)
    body  = fields.TextField(default="")

create_all(Post)
```

```python
# Api/v1/Post/Post.py   (POST /v1/post)
from endocore import Request, Response
from Models.blog import Post

async def handler(request: Request) -> Response:
    data = await request.json()
    post = Post.objects.create(title=data["title"], body=data.get("body", ""))
    return Response.json({"id": post.pk, "title": post.title}, status=201)
```

Two things worth understanding here, not just copying:

- **`configure()` and `create_all()` run once, the first time `Models.blog`
  is imported** — Python caches modules in `sys.modules`, so no matter how
  many different handler files do `from Models.blog import Post`, the
  module body (and therefore `configure`/`create_all`) executes exactly
  once, at whichever moment the *first* import happens (in practice: during
  boot, since EndoCore eagerly imports every discovered handler). This is
  why the example works with zero explicit "app startup" wiring.
- **Call `configure()` for the `"default"` connection in exactly one place**
  — if two different model files both call `configure(backend="sqlite",
  database=...)` for the same alias, whichever one Python happens to import
  *second* silently replaces the first connection (`configure()` always
  overwrites; see [Transactions](../orm/transactions.md)). Keep one file
  (this one, `Models/blog.py`, or a dedicated `Models/db.py` in a bigger
  app) as the single place that calls `configure()`, and have every other
  model file just `import fields, Model` and rely on that one having already
  run.

`blog.db` is created **relative to the process's current working
directory** (wherever you ran `endo dev` from), not relative to the model
file — worth knowing before you wonder why the file shows up somewhere
unexpected. See the full [ORM guide](../orm/index.md) for fields, lookups,
relations, and the async API.

## 7. Inspect your app

```bash
endo routes         # list every route + the file it maps to
endo check          # find broken handlers, duplicate routes, skipped files (with reasons)
endo openapi        # print the OpenAPI schema
```

`endo check` is worth running any time something *should* be routed but
isn't showing up — it prints exactly why the scanner skipped each such file
(wrong version folder, wrong location), rather than leaving you to guess.

That's the whole loop. Next, follow the [Tutorial](tutorial.md) to build a
complete, versioned API with services, middleware and migrations.
