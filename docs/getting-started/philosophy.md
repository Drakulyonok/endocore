# Philosophy

A few decisions explain everything else about EndoCore.

## The folder tree is the API

Routing, versioning and the CLI are one mechanism, not three. All of them work
on the `Api/` directory:

- a folder is a URL segment
- a file name is an HTTP method (`Get.py`, `Post.py`, …)
- a `[id]` folder is a dynamic segment
- the first `vN` folder is the API version

There is one source of truth — the tree — so code and routes can't drift apart.
What you see in the folder is what the server serves.

## Thin endpoints, logic in services

An endpoint should parse input, call a service, and return a response. Nothing
else.

This isn't a style preference. Versioning works by copying endpoint files, so
any business logic inside them gets duplicated with every new version. Keep the
logic in services and a new version stays a thin skin over the same core.

## Versions are folders

A version is a `vN` folder, not a field in a config. `v1` and `v2` are separate
trees, so creating `v2` physically cannot change how `v1` behaves. Old clients
keep working — guaranteed by the layout, not by discipline.

## One core dependency

The core needs exactly one external package: `uvicorn`, the HTTP transport.
The resolver, loader, Request/Response, middleware, ORM and CLI are all written
on the standard library. PostgreSQL, encrypted files, Redis, Celery and
pydantic are optional extras.

Writing our own HTTP server would add nothing to the idea. `uvicorn` is where
"from scratch" reasonably stops.

## Security by default

The ORM binds every value through the driver, validates and quotes every
identifier, accepts only known lookups, escapes `LIKE` wildcards, and coerces
`LIMIT`/`OFFSET` to integers. The logger masks passwords and tokens before
anything is written. Encrypted files are useless without the key.

None of this needs to be turned on.

## One broken file doesn't kill the app

If an endpoint file fails to import, the error goes into the boot summary and
the rest of the app starts normally. `end check` shows what's broken.

---

To see these ideas in practice, start with the [Quickstart](quickstart.md) or
build a small app in the [Tutorial](tutorial.md).
