# Philosophy

EndoCore is built on a few firm decisions. They explain why it looks the way it
does — and why it *doesn't* do some things other frameworks do.

## 1. The folder tree is the API

Routing, versioning and the CLI are **not three subsystems** — they are
different operations over **one abstraction**: the `Api/` directory tree.

- A **folder** is a URL segment.
- A **file name** is an HTTP method (`Get.py`, `Post.py`, …).
- A **`[id]` folder** is a dynamic segment.
- The first **`vN` folder** is the API version.

Because there is exactly one source of truth (the tree), code and routes can
never drift. What you see is what you serve.

## 2. Thin endpoints, logic in services

Endpoints must be thin: *parse input → call a service → return a response.*
This isn't aesthetics — it's a functional requirement of versioning. If logic
lives in endpoint files, every new version becomes a copy-paste of that logic.
Services are the reusable core; endpoints are the thin, versioned skin.

## 3. Versions are folders, not metadata

A version applies to the **whole endpoint with all its methods**. Its home is a
`vN` folder, not a field inside a file. `v1` and `v2` coexist, and after `v2` is
created, `v1` behaves **identically** to before. If a change in `v2` could touch
`v1`, the versioning would be fake.

## 4. One core dependency

The core takes exactly one thing from outside: **`uvicorn`** — the HTTP
transport. Everything that *is the idea* (resolver, loader, Request/Response,
middleware, ORM, CLI) is written from the standard library. Writing your own TCP
server or HTTP parser is a different planet and adds nothing to the idea;
`uvicorn` is the right "from scratch" boundary.

Optional capabilities (PostgreSQL, encrypted files, Redis, Celery, pydantic) are
**opt-in extras**, never forced on the core.

## 5. Security is not a feature you add later

The ORM binds every value through the driver, validates and quotes every
identifier, whitelists lookups, escapes `LIKE` wildcards, and coerces
`LIMIT`/`OFFSET` to integers. Logs mask sensitive keys before anything is
written. Encrypted files can't be recovered from a leaked disk without the key.
These are defaults, not options.

## 6. Boot never dies from one broken file

A single handler that fails to import must not bring down the whole app. Import
errors are collected and reported in a boot summary — the rest of the app keeps
serving.

## What EndoCore deliberately does not do

- **No GraphQL.** It contradicts the file-as-route idea. Routes are files;
  a single opaque `/graphql` endpoint isn't.
- **No admin panel.** Out of scope.
- **No heavy metaprogramming in endpoints.** The magic lives in the tree walk,
  not in your handlers.
