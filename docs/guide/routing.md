# Routing

The router is the heart of EndoCore. There is no route table you maintain — the
**folder tree is the route table**.

## The rules

| Filesystem | URL |
|-----------|-----|
| `Api/v1/User/Role/Get.py` | `GET /v1/user/role` |
| `Api/v1/User/Role/Post.py` | `POST /v1/user/role` |
| `Api/v1/User/[id]/Get.py` | `GET /v1/user/42` → `id = "42"` |
| `Api/v2/User/Role/Post.py` | `POST /v2/user/role` |

- **Folder = URL segment.** Folder names are lower-cased when matched
  (`User` → `user`), so you can keep PascalCase on disk.
- **File name = HTTP method.** `Get.py`, `Post.py`, `Put.py`, `Patch.py`,
  `Delete.py`, `Head.py`, `Options.py`. Normalized via `.upper()`.
- **`[name]` folder = dynamic segment**, captured into `request.path_params`.
- **First `vN` segment = version** (see [Versioning](versioning.md)).

## Handler contract

Each endpoint file defines a `handler`:

```python
from endocore import Request, Response

async def handler(request: Request) -> Response:
    return Response.json({"ok": True})
```

- `handler` may be `async def` or a plain `def`.
- It may take just `request`, or use [dependency injection](dependency-injection.md)
  for extra parameters.
- It returns a `Response`, or a `dict`/`list` (→ JSON 200), a `str` (→ text),
  `None` (→ 204), or `(content, status[, headers])`.

An optional `def init(): ...` runs once at boot for setup.

## Static beats dynamic

If both a static folder and a `[id]` folder could match, the **static** one
wins:

```text
Api/v1/User/Me/Get.py       # GET /v1/user/me   -> the static handler
Api/v1/User/[id]/Get.py     # GET /v1/user/42   -> the dynamic handler
```

## Resolution outcomes

- **200** — matched.
- **404** — no such path or version (a version-less request is 404 by default).
- **405** — the path exists but not for that method (with an `Allow` header).

## Non-route files

Files whose name isn't an HTTP method are **not** endpoints — they're normal
modules (services, helpers). Files under a `Services/` folder are never treated
as routes.

## Inspecting routes

```bash
end routes      # every method + URL + the file it maps to
end check       # duplicate routes, broken handlers, skipped files
```

## Default-to-latest (opt-in)

By default a request without a `vN` prefix is a 404 ("explicit over implicit").
You can opt in to resolving version-less paths to the newest version:

```bash
end dev --default-version latest
```

Every such request is **logged** with the version it was served by.
