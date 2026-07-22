# Routing

The router is the heart of EndoCore. There is no route table you write and
maintain by hand — the **folder tree under `Api/` *is* the route table**. This
page explains the rule in full, including every edge case the resolver
actually implements (verified against `endocore/core/discovery.py`,
`endocore/core/router.py` and `endocore/core/registry.py` — this isn't
"roughly how it works", it's exactly how it works).

## The mental model

At boot, EndoCore does **one** filesystem walk over `Api/` (`rglob("*.py")`,
so it recurses into every subfolder). For every `.py` file it finds, it looks
at the file's **name** and its **path** and decides one of three things:

1. It's an **endpoint** — its file name matches an HTTP method, it lives
   under a version folder, and it's not inside a folder that opts out of
   routing. It gets turned into a route.
2. It's **skipped with a reason** — it *looks* like it was meant to be a
   route (the name matches a method) but something about its placement is
   wrong (missing version folder, inside `Services/`). This shows up in
   `end check` and in the boot log.
3. It's **ordinary code** — its file name isn't an HTTP method at all
   (`validator.py`, `create_role.py`, `__init__.py`, ...). EndoCore doesn't
   look at it during routing at all; it's just a Python module you can
   import normally. This case is *not* logged anywhere, because it isn't an
   error — it's the overwhelmingly common case (most files in a real app
   aren't endpoints).

Nothing is registered, decorated, or listed in a config file. The **existence
of the file, at that path, with that name** is the entire route registration.

## The rule, precisely

| Filesystem | URL |
|-----------|-----|
| `Api/v1/User/Role/Get.py` | `GET /v1/user/role` |
| `Api/v1/User/Role/Post.py` | `POST /v1/user/role` |
| `Api/v1/User/[id]/Get.py` | `GET /v1/user/42` → `id = "42"` |
| `Api/v2/User/Role/Post.py` | `POST /v2/user/role` |

Breaking that down segment by segment:

### 1. The first path segment must be a version

The **first folder** directly under `Api/` must match the regex `^v\d+$`
(e.g. `v1`, `v2`, `v17`) — a lowercase `v` followed by one or more digits,
nothing else. This is checked with Python's `re.match`, which is
**case-sensitive**: a folder named `V1` does **not** match, and every file
under it is skipped with the reason *"not under a version folder (vN)"*
(you'll see this in `end check`'s output — it's a common first-time typo).

There's no allowance for `v1.2` or `v1-beta` either — the version segment is
strictly "v" + digits. See [Versioning](versioning.md) for what a version
means semantically (it's not just a URL prefix — `v1` and `v2` are
independent copies of everything below them).

### 2. Every folder between the version and the file is a URL segment

Each intermediate folder becomes one path segment, **lower-cased**:

```
Api/v1/User/Role/Get.py
        ^^^^ ^^^^
        User Role   ->  segments: "user", "role"  ->  /v1/user/role
```

So `User` and `user` and `USER` on disk all resolve to the exact same URL
segment `user` — case on disk is purely a style choice (PascalCase folders
read nicely in an IDE's file tree; the URL is always lowercase). This means
two folders that differ only by case (`Api/v1/User/Get.py` and
`Api/v1/user/Get.py`) **collide**: both produce the identical URL
`/v1/user`, so whichever file the filesystem walk visits **second** silently
overwrites the first one's handler for that method (insertion order is
deterministic — files are visited in sorted path order — but which one
that is isn't obvious at a glance). The good news: this exact class of
mistake **is** caught by `end check`, which reports
`[dup] GET /v1/user defined more than once` — always run it after a rename.

### 3. The file's name (its **stem**, not its extension) is the HTTP method

`Get.py`, `Post.py`, `Put.py`, `Patch.py`, `Delete.py`, `Head.py`,
`Options.py` — the stem is upper-cased and matched against exactly this set:
`{GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS}`. `get.py`, `GET.py`, `Get.py`
are all equivalent (the *file name's* case doesn't matter, unlike folder
names, which matter for readability only in the same lower-cased-anyway way).

A file whose stem doesn't match one of those — `validator.py`, `Utils.py`,
`__init__.py` — is simply not a route. EndoCore doesn't import it during
routing, doesn't log it, doesn't care about it. It's exactly as if it wasn't
under `Api/` at all, *except* that if it lives under a folder that shares a
name with a route folder, that's fine too — `Api/v1/User/create_role.py`
sitting right next to `Api/v1/User/Get.py` causes no conflict whatsoever.

**WebSockets** use a different set of stems: `Socket.py`, `Ws.py`, or
`Websocket.py` (also case-insensitive on the stem) map to a special
`WEBSOCKET` pseudo-method instead of a normal HTTP verb. See
[WebSockets](websockets.md).

### 4. A folder named `[name]` is a dynamic segment

The folder name must match `^\[(?P<name>[^\[\]]+)\]$` — square brackets around
one or more characters that aren't themselves brackets. Whatever text sits
between the brackets becomes the **path parameter's name**, verbatim,
**without lower-casing**:

```
Api/v1/User/[id]/Get.py         -> path_params["id"]
Api/v1/Order/[OrderId]/Get.py   -> path_params["OrderId"]   (case preserved!)
```

This is the one place in the whole routing tree where case is *not*
normalized — because that text has to double as a real handler parameter
name for [dependency injection](dependency-injection.md) to auto-inject it.
If you want `user_id = Depends(...)`-style auto-injection by name to work,
keep the bracket content a valid Python identifier (`[id]`, `[user_id]`).
Anything else — `[user-id]` (a hyphen isn't valid in an identifier) — still
*works* as a dynamic segment, but you can only read it via
`request.path_params["user-id"]`, never as a same-named function parameter.

The captured value itself is always a `str` (URL-decoded — see
[Query strings and path params](#url-decoding) below) — cast it yourself
(`int(request.path_params["id"])`) if you need a number, or rely on
`request.path_params["id"]` inside a plain handler.

### 5. Static folders beat dynamic ones when both could match

```
Api/v1/User/Me/Get.py       # GET /v1/user/me   -> the static "Me" handler wins
Api/v1/User/[id]/Get.py     # GET /v1/user/42    -> the dynamic handler
```

The resolver is a trie (see [Architecture](architecture.md#the-resolver-the-heart)):
walking `/v1/user/me`, at the `User` node it first checks whether a *static*
child named `me` exists; only if none does, it falls back to the dynamic
child (if one was registered). This means you can special-case one specific
value (`me`, `current`, `0`) alongside a catch-all `[id]` without any extra
configuration — just add both folders. There's no ambiguity to resolve at
request time, because static lookup always wins, unconditionally.

**Only one dynamic child is allowed per node — and unlike the static case
above, a name clash here is *not* caught by `end check`.** If both
`Api/v1/User/[id]/Get.py` and `Api/v1/User/[slug]/Post.py` exist, the trie
node for "User's dynamic child" is created once, by whichever file the
scanner visits **first** (sorted path order), and its `param_name` is set
from *that* file's bracket name and never changed again — the second
file's own bracket name is silently ignored for routing purposes. Concretely:
if `Get.py` under `[id]` is registered first, then the `Post.py` handler
living in the `[slug]` folder still receives `request.path_params["id"]`,
**not** `"slug"`, even though its own folder is named `[slug]`. `end check`'s
duplicate detector doesn't catch this because it compares full URL
*templates* (`/v1/user/{id}` vs `/v1/user/{slug}`), which are different
strings — from `end check`'s point of view nothing is duplicated. Avoid this
entirely by using the **same bracket name at every method file sharing a
tree position** (`[id]` for `Get.py`, `Patch.py`, and `Delete.py` alike).

## Handler contract

Each endpoint file defines one thing: a callable named `handler`.

```python
from endocore import Request, Response

async def handler(request: Request) -> Response:
    return Response.json({"ok": True})
```

- `handler` may be `async def` (recommended — see
  [why](background-lifecycle.md)) or a plain `def`; **sync handlers are
  dispatched to a worker thread** automatically so a blocking body can't
  stall the event loop for other in-flight requests. Async handlers stay on
  the loop.
- The simplest signature is exactly one parameter named `request` with no
  default — the dispatcher special-cases this ("trivial handler") and calls
  it directly, skipping the full dependency-resolution machinery entirely
  for a small performance win. Anything more elaborate — extra parameters,
  `Depends(...)`, a path-param-named argument — goes through
  [dependency injection](dependency-injection.md) instead.
- Return value coercion: a `Response`/`StreamingResponse` is used as-is; a
  `dict`/`list` becomes a JSON 200; a `str` becomes a `text/plain` 200;
  `None` becomes an empty `204`; a tuple `(content, status)` or
  `(content, status, headers)` builds a `Response` from those parts.
- An optional module-level `def init(): ...` (no parameters) runs **once**,
  at boot, right after the handler module is imported — a place for
  one-time setup local to that single endpoint file. It's called as a plain
  synchronous call (`init()`), **not awaited** — if you define it as
  `async def init(): ...`, that call just creates a coroutine object and
  discards it without ever running the body (Python prints
  `RuntimeWarning: coroutine 'init' was never awaited`). Keep `init` a plain
  `def`.

## Non-route files and the `Services/` opt-out

Any file whose stem isn't an HTTP-method name (or a WebSocket stem) is
invisible to the router, **anywhere** in the tree — you don't need to do
anything special to keep `Api/v1/User/Services/create_role.py` or
`Api/v1/User/validators.py` from becoming routes; their names alone
(`create_role`, `validators`) already disqualify them.

The one situation that *does* need an explicit opt-out is when a helper file
would otherwise *look* like a route — e.g. you keep a small local
`Get.py`-named helper that isn't meant to be an endpoint. For that, put it
inside a folder literally named `Services` (exact case — `services` does
**not** match) anywhere along the path; `discovery.py` checks every
intermediate folder name against `{"Services", "__pycache__"}` and skips the
whole file (with the reason *"inside non-route folder 'Services'"*) if any
of them match. This is also how **local, per-version services** work: a
`Services/` folder inside `Api/v1/User/` holds code that's global-import-able
but never treated as a route and gets copied along with the version when you
run `end version create`.

## Resolution outcomes

A request resolves to exactly one of three outcomes:

- **200** — a handler exists for this exact method + path. Runs normally.
- **404** — no such path exists at all for *any* method, **or** the request
  has no recognizable version prefix (`^v\d+$`) — a version-less request is
  404 by default (see [Default-to-latest](#default-to-latest-opt-in) to
  change this), **or** the version exists but the path under it doesn't.
- **405 Method Not Allowed** — the path exists (some *other* method has a
  handler there), but not for the method you used. The response carries an
  `Allow` header listing every method that *does* have a handler at that
  exact path, e.g. `Allow: GET, POST`.

## URL decoding

Path segments are URL-decoded before matching (`urllib.parse.unquote`), so
`/v1/user/O%27Brien` resolves `id` to the literal string `O'Brien`, not the
percent-escaped form. Empty segments are dropped — `/v1//user` and `/v1/user`
and `/v1/user/` all split into the same segment list, so trailing/doubled
slashes are harmless.

## Inspecting and debugging routes

```bash
end routes      # every method + URL + the file it maps to, straight from the trie
end check       # duplicate routes, broken handlers, and every skipped file with its reason
end doctor      # broader project sanity check (Python version, optional deps, layout)
```

`end check` is the fastest way to find a typo'd version folder or a
misplaced file: anything discovery.py skipped with a reason shows up there,
even though it never affects the running app (a skipped file just means
"not a route" — it isn't an error by itself).

## Default-to-latest (opt-in)

By default a request without a `vN` prefix is a 404 — EndoCore's stance is
"explicit is better than implicit", and silently guessing a version for a
client that forgot to specify one is exactly the kind of implicit behavior
that causes production incidents down the line. You can opt in anyway:

```bash
end dev --default-version latest
```

or in code: `Application(app_dir=..., default_version="latest")`. With this
set, a version-less request is retried against the newest registered
version (`max` by numeric suffix, so `v10` beats `v2`), and **every time this
fallback actually serves a request, it's logged** — `no version in GET
/user/role -> served v3` — specifically so that "which version is my
version-less traffic secretly hitting" is never a silent mystery. An
explicit-but-unknown version (`/v99/...`) is still a plain 404: this fallback
only ever triggers when the request has **no** version segment at all.
