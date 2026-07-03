# Changelog

All notable changes to EndoCore are documented here.

## [0.3.0b1] — 2026-07-03 — third Beta: ORM completeness, encrypted files, deferrals

### Added — ORM
- **Many more field types**: `SmallIntegerField`, `PositiveSmallIntegerField`,
  `PositiveIntegerField`, `PositiveBigIntegerField`, `BigAutoField`, `SlugField`,
  `EmailField`, `URLField`, `GenericIPAddressField`, `UUIDField`, `JSONField`
  (JSONB on Postgres), `BinaryField`, `TimeField`, `DurationField`.
- **Validators** run on the write path (`save`/`create`/`update`): `choices`,
  length, positivity, email/URL/slug/IP formats; `full_clean()`.
- **Encrypted `FileField`** — files stored in any folder, **encrypted at rest**
  with AES-256-GCM. The DB keeps only an opaque key; if the storage leaks the
  files are unrecoverable without the separate key, and tampering is detected.
  `configure_storage(root=..., key=...)`, `generate_key()`.
- **Relational queries**: cross-table lookups (`filter(city__country__name=...)`)
  and ordering across relations via LEFT JOINs, plus `select_related(...)`.
- **Expressions**: `F` (`update(views=F('views') + 1)`) and aggregates
  `aggregate(Count/Sum/Avg/Min/Max)`.
- **QuerySet**: `distinct()`, `earliest()`/`latest()`, `get_or_create()`,
  `update_or_create()`, single-statement `bulk_create()`, `db_index` + index DDL.

### Added — framework (first-Beta deferrals)
- **Default-version alias** (opt-in): `Application(default_version="latest")` /
  `end dev --default-version latest` resolves a version-less path to the newest
  version and logs which one served it (strict 404 stays the default).
- **Request streaming** (`Request.stream()`) and `StreamingResponse`.
- **In-process dev watcher** (`watchfiles`) rebuilds the route tree on change
  without a process restart (`Application.reload()`).
- **`end test`** now passes pytest flags directly (`end test -q -k name`).

### Changed
- Optional extras: `endocore[files]` (cryptography), `endocore[watch]`.
- Version -> 0.3.0b1. 102 tests total.

## [0.2.0b1] — 2026-07-03 — second Beta: the ORM

A small, secure, Django-flavoured ORM for **SQLite** and **PostgreSQL**.

### Added
- **Models** — declarative `Model` classes with a metaclass and `_meta`; fields:
  `AutoField`, `IntegerField`, `BigIntegerField`, `CharField`, `TextField`,
  `BooleanField`, `FloatField`, `DecimalField`, `DateTimeField` (`auto_now`),
  `DateField`, `ForeignKey` (lazy related-object load).
- **QuerySet** — lazy & chainable: `filter/exclude/get/all/order_by/values/
  values_list/count/exists/first/last/create/update/delete/bulk_create`, slicing
  for `LIMIT`/`OFFSET`, and **Q objects** (`&`, `|`, `~`).
- **Lookups** — `exact iexact contains icontains startswith istartswith endswith
  iendswith gt gte lt lte in isnull range`.
- **Backends** — `sqlite` (stdlib) and `postgres` (`psycopg`), sharing one
  security-critical base; correct per-dialect placeholders, quoting, autoincrement
  and `RETURNING`/`lastrowid`.
- **Connections & transactions** — `configure()` / `connect()`, lazy open,
  `with atomic():` blocks; credentials never logged.
- **Schema** — `create_table` / `create_all` / `drop_table` DDL from models.
- **Security (the focus)** — values are always driver-bound (never formatted into
  SQL); identifiers validated (`^[A-Za-z_]\w*$`) and quoted; lookups are a strict
  whitelist; LIKE wildcards in user input escaped with `ESCAPE`; `LIMIT`/`OFFSET`
  coerced to ints. 34 ORM tests including explicit injection tests.
- **Example** — `Post` model + ORM-backed `GET`/`POST /v1/post` endpoints.

### Changed
- `endocore[postgres]` optional extra for the psycopg driver.

## [0.1.0b1] — 2026-07-03 — first Beta

First usable Beta. The framework boots a real app, serves it over uvicorn, and
the CLI scaffolds and versions the tree.

### Added
- **File-based routing** — folder = URL segment, file = HTTP method, `[id]` =
  dynamic segment. Single tree-walk (`Api/` via `rglob`) builds a cached route
  trie at boot.
- **Versioning** — first path segment `^v\d+$`; `v1`/`v2` coexist. A request
  without a version prefix is a 404 (explicit over implicit).
- **Own `Request` / `Response`** over the raw ASGI scope (no Starlette).
- **Middleware chain** (onion / `call_next`). Built-in logging middleware is
  always outermost; user middleware is auto-loaded from `Middleware/__init__.py`
  (an ordered `middlewares` list).
- **`HTTPError`** — handlers can `raise HTTPError(status, detail)` to
  short-circuit with a status code.
- **Logging** — stdlib wrapper; every request logged with timing and a
  **masked** payload (`password`, `token`, `authorization`, … → `***`).
- **Boot resilience** — one broken handler file is collected into a boot-error
  summary, not fatal.
- **CLI `end`** — `create`, `dev` (uvicorn + reload), `version create`/`list`,
  `test`. `version create` copies endpoints + local services (never global
  `Services/`) and rewrites `Api.vSRC` → `Api.vDEST` imports so a new version
  uses its own local services (real isolation).
- **Framework test suite** (`tests/`, 29 tests) and a runnable `example/` app.

### Known limitations
- `end test` needs `--` before pytest flags: `end test -- -q -k name`.
- No default-to-latest version alias, no request-body streaming, no
  `pydantic` validation, no custom `watchfiles` watcher (uses uvicorn reload).
  These are intentionally deferred.
