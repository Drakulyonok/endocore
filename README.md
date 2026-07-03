# EndoCore

**File-based ASGI backend framework — the folder tree *is* the API.**

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

## Getting started

```bash
py -3 -m pip install -e .
cd example
end dev
```
