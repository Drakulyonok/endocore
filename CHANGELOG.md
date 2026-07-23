# Changelog

All notable changes to EndoCore are documented here.

## [0.9.0b1] — 2026-07-24 — security audit: response-splitting, cache RCE, CSWSH, ORM races, and a dev-mode-by-default footgun

**1756 tests.** This release is the result of a deliberately adversarial pass
over the whole framework — not just reading code, but reproducing each
exploit before the fix and again after, and in one case catching a regression
in the fix itself before it shipped. `bandit` and `pip-audit` now run in CI on
every push, and the request parsers (multipart, JSON, query string) were
property-fuzzed with `hypothesis`.

### Security

- **HTTP response splitting (CWE-113)** — `Response` and `StreamingResponse`
  now reject (`ValueError`) any header name, header value, cookie component,
  or `media_type` containing a raw CR, LF, or NUL, enforced unconditionally at
  the point the response is built rather than left to the ASGI server to catch.
- **Pickle RCE in the Redis cache (CWE-502)** — `RedisCache.get()` called
  `pickle.loads()` on whatever bytes Redis returned, unauthenticated; anything
  that could write that key got code execution on the next read. Pass
  `secret=` to `CacheExtension`/`configure_cache("redis", ...)` to HMAC-sign
  every value, bound to its own cache key so a signed blob can't be copied to
  a different key and still verify. Without `secret=`, behavior is unchanged
  but now raises a warning.
- **Cross-site WebSocket hijacking** — the handshake had no `Origin` check at
  all, so a page on any other site could open a websocket to your app and
  ride along on a cookie-based session. Same-origin is now enforced by
  default outside `dev=True` (relaxed automatically in dev, since a local
  frontend on another port is a different origin); configure
  `Application(ws_allowed_origins=[...])` explicitly for a real cross-origin
  frontend.
- **`create_app()` defaulted to `dev=True`** — the ASGI factory that
  `uvicorn endocore.asgi:create_app --factory` (the documented production
  entry point) uses defaulted dev mode **on** when `ENDOCORE_DEV` wasn't set
  at all, silently exposing `/docs`, the dev file watcher, and the relaxed
  websocket origin check. `Application` itself already defaulted to
  `dev=False`; the factory now matches it. `endo dev` is unaffected — it
  already set the env var explicitly either way.
- **Two ORM race conditions leaked driver exceptions under concurrency** —
  `get_or_create()`/`update_or_create()` and `ManyRelatedManager.add()` (M2M)
  could raise an uncaught `IntegrityError` when two callers raced the same
  not-yet-existing row/relation. Both now catch the race, verify the row/pair
  actually exists now, and return the existing result instead of raising —
  verified by reproducing the race with real concurrent threads before and
  after the fix.
- **`bulk_update()` skipped field validation** — unlike `save()`, `.update()`,
  and `bulk_create()`, it wrote values straight to SQL with no `choices`,
  required-ness, or custom-validator check. A `role` field restricted to
  `choices=[...]` could be set to an arbitrary string through the bulk path.
- **`Model.__repr__` printed secrets** — a `password_hash`-shaped column could
  end up readable in a stray `print(user)`, a traceback, or a debugger.
  Masked by field name, the same way `Settings.__repr__` already worked.
- **Log masking only matched exact key names** — `old_password`,
  `X-Api-Key`, and `refresh_token` all bypassed masking because only a field
  literally named `password`/`api_key`/... was ever caught. Matching is now
  by substring, case/separator-insensitive.
- **CSRF token comparison wasn't constant-time** — `cookie != header` is now
  `hmac.compare_digest`, matching every other secret comparison in the codebase.
- **Connection pool exhaustion hung forever** — `Connection._acquire()` waited
  on an unbounded `threading.Condition`; a genuinely exhausted or stuck pool
  blocked every caller (and the worker thread behind it) indefinitely with no
  diagnostic. Added `pool_timeout` (default 30s) → `PoolTimeoutError` instead.
- **Background task (`Response(..., background=...)`) failures vanished** —
  an exception there is now logged (with the same request id as the original
  request) instead of propagating silently past an already-sent response.
- **Swagger UI supply-chain risk** — `/docs` loaded JS/CSS from an unversioned
  `unpkg.com` URL with no integrity check. Pinned to a specific
  `swagger-ui-dist` version with real, computed Subresource Integrity hashes.
- **Malformed request bodies crashed instead of failing clean** — a non-UTF-8
  multipart field, a non-Latin-1 multipart boundary, a non-UTF-8
  `application/x-www-form-urlencoded` body, and a pathologically deep JSON
  array all raised an unhandled `UnicodeDecodeError`/`UnicodeEncodeError`/
  `RecursionError` instead of the framework's own `BadRequest` convention
  (none of these leaked info or crashed the process — `logging_middleware`'s
  top-level handler already contained them — but all four now resolve to a
  clean 400, found by fuzzing the parsers with `hypothesis`).
- **`cryptography` CVE** (GHSA-537c-gmf6-5ccf, vulnerable statically-linked
  OpenSSL) — minimum version raised from `>=41` to `>=48.0.1`.

### Added
- **`ip_allowlist_middleware(allowed=[...])`** — restrict a backend to known
  callers by source IP/CIDR (v4 and v6) rather than trusting a spoofable
  header; composes with `proxy_headers_middleware` for real client IPs behind
  a reverse proxy.
- **CI `security` job** — `bandit` (static analysis) and `pip-audit`
  (dependency CVEs) run on every push/PR alongside the test matrix.

### Fixed
- **`ManyRelatedManager.set()` wasn't atomic** — `clear()` and `add()` ran as
  separate operations; a failure in `add()` left the relation cleared instead
  of rolled back. Now one transaction.

## [0.8.0b1] — 2026-07-23 — data migrations, distributed rate limit, WebSocket fan-out

**1696 tests (plus PostgreSQL pool tests behind ENDOCORE_TEST_POSTGRES_DSN and
a Redis-backed rate-limit/pub-sub concurrency test behind
ENDOCORE_TEST_REDIS_URL — both now run for real in CI, against service
containers).**

### Added
- **`prefetch_related` on reverse FK relations** — `Author.objects.prefetch_related("books")`
  now batch-loads the reverse side in one extra query (previously only
  forward FK and M2M were supported; reverse access fell back to one query
  per instance). A bare `.all()` or plain iteration on the reverse manager
  reads the prefetched cache; any further chaining (`.filter()`, `.exclude()`,
  ...) re-queries, same as the forward/M2M prefetch already worked.
- **Data migrations** — `endo makemigrations <name> --python` writes a
  `forward(conn)`/`reverse(conn)` stub numbered into the *same* history as
  schema (JSON) migrations, so `migrate`/`rollback`/`showmigrations` order and
  track a data transformation together with the schema change it depends on,
  instead of a one-off script run by hand. Runs inside its own `atomic()`
  block; a raised exception rolls back and the migration isn't recorded as
  applied. Omit `reverse` (the generated stub raises) for a migration that
  can't be undone — `rollback` then fails loudly instead of doing nothing.
- **Distributed rate limiting** — `rate_limit_middleware(..., redis_client=...)`
  shares one counter across every worker process via Redis's atomic `INCR`,
  instead of each process enforcing its own independent in-memory limit
  (which under N workers silently turns a "100 req/min" limit into
  "100·N req/min"). Omit `redis_client` and behavior is unchanged
  (in-memory, per-process). The Redis client's synchronous calls are
  offloaded via `asyncio.to_thread`.
- **Multi-process WebSocket fan-out** — `WebSocketManager(redis_client=...)`
  publishes broadcasts to Redis (origin-tagged to avoid a worker re-delivering
  its own message to itself) so every worker's room delivers to its own local
  sockets. `await manager.start()` / `await manager.stop()` manage the
  background subscriber; wire them into `on_startup`/`on_shutdown`. Without
  `redis_client`, both are no-ops and behavior is unchanged (single process).
- **CI now runs against real PostgreSQL and Redis** — service containers
  (`postgres:16`, `redis:7`) with health checks, so the pool-concurrency and
  distributed rate-limit/pub-sub tests exercise real servers on every push
  instead of only when a contributor happens to run them locally.

### Changed
- **`end` console script removed — `endo` is the only entry point.** `end` was
  kept as a bash/cmd/zsh-only alias because it's a reserved word in
  PowerShell (`begin`/`process`/`end` blocks make a bare `end dev` a parser
  error there); maintaining two names for one command wasn't earning its
  keep. Reinstall the package (`pip install -e .` or `pip install
  endocore==0.8.0b1`) to pick up the change; scripts/CI invoking `end` need
  to switch to `endo`.

## [0.7.0b2] — 2026-07-22 — README/metadata refresh

No code changes — PyPI has no way to update a README on an already-published
release, and the README was substantially rewritten (as a proper pitch, with
a Discord link) after 0.7.0b1 was uploaded. This release exists solely to
carry that README to PyPI. See 0.7.0b1 just below for the actual feature set.

## [0.7.0b1] — 2026-07-22 — connection pooling, `aatomic()`, built-in auth

**1679 tests (plus 3 PostgreSQL pool tests behind ENDOCORE_TEST_POSTGRES_DSN).**

### Fixed
- **Transaction isolation under concurrency** — a transaction now holds the
  connection's lock for its whole block; concurrent threads (including the
  async threadpool) can no longer interleave statements inside someone else's
  open `atomic()`, and autocommit writes wait for the transaction to finish.
  Ownership is tracked with a `contextvars` token, so `a*` ORM calls join the
  transaction they were started in.
- **Sync handlers no longer block the event loop** — plain `def handler(...)`
  endpoints (and sync `background=` tasks) are dispatched via
  `asyncio.to_thread`; async handlers stay on the loop.
- **Rate limiter memory** — `rate_limit_middleware` sweeps expired client
  windows (at most once per window) instead of growing without bound.
- **Unicode case-insensitive lookups on SQLite** — `iexact`/`icontains`/... now
  fold non-ASCII text (Кириллица etc.): the connection registers a
  Unicode-aware `lower()` overriding SQLite's ASCII-only built-in.
- **ForeignKey to non-integer pks** — FK assignment, row loading (`to_python`),
  value binding (`to_db`) and the DDL column type now delegate to the target
  model's pk field, so FKs to `UUIDField` pks work end-to-end.
- `QuerySet.in_bulk` type hints no longer reference an unimported name.
- **FK lookups/assignment by attname** — `filter(owner_id=pk)` and
  `Model(owner_id=pk)` now resolve a ForeignKey by its `<name>_id` attname
  (Django-style), not just by the relation name.
- **SQLite results are fetched at execute time** — sqlite3 cursors read
  lazily and a concurrent thread's `rollback()` on the shared connection
  reset pending statements, so a SELECT fetched after its connection went
  back to the pool could silently come back empty (surfaced by the shop
  demo's idempotency race). Results are now materialized before release.

### Changed
- **`/docs` + `/openapi.json` are dev-only by default** — `Application(openapi=None)`
  serves them only when `dev=True`; opt in for production with `openapi=True`
  or `ENDOCORE_OPENAPI=1`.

### Added
- **`aatomic()`** — async transaction block (`async with aatomic(): ...`):
  same semantics as `atomic()` (SAVEPOINT nesting included) with the lock
  acquisition and commit/rollback offloaded so the event loop never blocks;
  `with atomic():` on the loop thread now emits a `RuntimeWarning`.
- **Connection pooling** — each alias owns a bounded pool of physical
  connections (`configure(..., pool_size=N)`; defaults: SQLite 1, PostgreSQL 5).
  A transaction pins one pooled connection for its whole block, so on
  PostgreSQL up to `pool_size` transactions run concurrently; autocommit
  statements borrow any free connection. PostgreSQL connections are rolled
  back before returning to the pool, so none sit "idle in transaction".
- **PostgreSQL pool race tests** — `tests/orm/test_postgres_pool.py`, gated by
  `ENDOCORE_TEST_POSTGRES_DSN`: proves genuine transaction concurrency,
  no-overdraft conditional spends and UNIQUE races on a real server before
  `pool_size > 1` is trusted in production.
- **Built-in auth** (stdlib-only):
  - `session_middleware(secret)` — stateless cookie sessions signed with
    HMAC-SHA256; `request.session` is a dict, the cookie is rewritten only
    when modified and deleted when cleared; tampered/expired cookies degrade
    to an anonymous session.
  - `hash_password` / `verify_password` / `needs_rehash` — scrypt
    (`hashlib.scrypt`, OWASP work factors) in a self-describing format so
    parameters can be raised later; constant-time verification, and
    `verify_password(pw, None)` burns a full derivation so login timing
    cannot enumerate which accounts exist.
  - `login(request, pk)`, `logout(request)`, `user_id(request)` and the DI
    dependency `require_user_id` (401 for anonymous) — all importable from
    `endocore`.
- **`py.typed`** — the package ships inline type hints (PEP 561); type
  checkers no longer need stub overrides.
- **`demos/`** — three end-to-end example apps exercising the framework under
  concurrency and real payment-style requirements (not shipped in the sdist):
  `teamboard` (kanban with live WebSocket updates), `booking` (slot booking
  with a race-tested no-double-booking guarantee), `shop` (idempotent
  purchases + payment-gateway webhook, race-tested for no-overdraft spends —
  see its README for the PostgreSQL pool run).

## [0.6.0b1] — 2026-07-03 — sixth Beta: async ORM, ws pub/sub, pydantic, migration alter/rename

**1632 tests.**

### Added
- **Async ORM** — non-blocking DB access for ASGI via a threadpool offload:
  `aget`, `acreate`, `acount`, `aexists`, `afirst`/`alast`, `alist`,
  `aupdate`/`adelete`, `aget_or_create`, `abulk_create`/`abulk_update`,
  `aaggregate`, async iteration (`async for ... in qs`), and instance
  `asave`/`adelete`/`arefresh_from_db`.
- **WebSocket pub/sub** — `WebSocketManager` with rooms:
  `connect`/`disconnect`/`broadcast`/`broadcast_json`/`send_to`, dead-connection
  cleanup (single-process; pair with Redis for multi-worker).
- **Pydantic integration** (`endocore[pydantic]`) — a handler param annotated
  with a `BaseModel` is validated from the JSON body (422 with field errors on
  failure); its JSON schema is included in the OpenAPI `requestBody`.
- **Migrations: column alter + rename** — a changed column definition triggers a
  portable table **rebuild** (data preserved, reversible); explicit column
  **rename** via `endo makemigrations --rename table.old=new` (`RENAME COLUMN`).

### Notes
- The async ORM uses a threadpool offload over the existing sync engine — one
  battle-tested query path, non-blocking for both SQLite and PostgreSQL.

## [0.5.0b1] — 2026-06-18 — fifth Beta: WebSockets, cache, OpenAPI, integrations, ORM/migrations maxed

**1600 tests.**

### Added — framework
- **WebSockets**: file-based routing via ``Socket.py`` (also ``Ws.py``); a
  ``WebSocket`` class (`accept`, `receive_text/json/bytes`, `send_*`,
  `iter_text/json`, `close`); DI-aware dispatch; unknown routes rejected (4404).
- **Cache layer**: `configure_cache` / `get_cache` with in-memory and Redis
  backends, TTL, `incr`, and a `@cached` decorator (sync + async).
- **OpenAPI 3.0**: `generate_openapi`, served at `/openapi.json` and Swagger UI
  at `/docs`; `endo openapi` writes/prints the schema.
- **Service integrations** (`endocore.extensions`): a pluggable `Extension`
  base + `extensions.py` loader (setup + lifespan), with shipped
  `RedisExtension`, `CeleryExtension`, `EmailExtension` (stdlib SMTP), and
  `CacheExtension`. Optional deps: `endocore[redis]`, `endocore[celery]`.

### Added — ORM
- **Reverse relations**: `author.book_set` / `related_name`, reverse OneToOne
  (`author.profile`).
- **`annotate()`** with aggregates over a field, a M2M, or a reverse FK
  (`Author.objects.annotate(n=Count("books"))`).
- **`only()` / `defer()`** (partial column fetch), **`bulk_update()`**.

### Added — migrations
- **Index diffing** (CREATE/DROP INDEX in migrations), **`endo showmigrations`**,
  **`endo sqlmigrate <name>`**, **`endo migrate <target>`**.

## [0.4.0b1] — 2026-05-30 — fourth Beta: client-usable (DI, batteries, migrations)

Big round toward "client usable": convenience, security, and a lot more surface.
**1510 tests.**

### Added — framework / HTTP
- **Dependency Injection**: `Depends(...)` (FastAPI-style, nested, per-request
  cached) + app-level providers by type or name (`providers.py`). Resolves
  string annotations via `get_type_hints`.
- **Unified config**: typed `Settings` (env-backed, secret-masked repr),
  `env()`, `load_dotenv()`.
- **HTTP exception classes**: `NotFound`, `Unauthorized`, `Forbidden`
  (=`PermissionDenied`), `BadRequest`, `Conflict`, `UnprocessableEntity`,
  `TooManyRequests`, `PayloadTooLarge`, `MethodNotAllowed` — rendered centrally.
- **Request**: `QueryParams` (`.get`/`.getlist`), `cookies`, `form()` +
  `files()` (urlencoded + multipart parser), `get_signed_cookie`, body-size limit.
- **Response**: `set_cookie`/`delete_cookie`/`set_signed_cookie`, `redirect`,
  `no_content`, background tasks; signed cookies (`Signer`, HMAC-SHA256).
- **Lifecycle**: `on_startup`/`on_shutdown` hooks (`hooks.py`); background tasks.
- **Logging**: framework `X-Request-ID`, colored dev logs.
- **Middleware bundle**: `cors`, `security_headers`, `gzip`, `proxy_headers`
  (trusted proxy), `rate_limit`, `timeout`, `csrf` (signed double-submit).

### Added — ORM
- **ManyToManyField** (auto through table, `add/remove/set/clear/all/count`),
  **OneToOneField**, **prefetch_related** (batch, no N+1), abstract models with
  field inheritance, `Meta.ordering` / `unique_together` / `indexes`.
- **Migrations with rollback**: `endo makemigrations` / `migrate` / `rollback`
  (forward+reverse SQL, applied-state table).
- `refresh_from_db`, `save(update_fields=...)`, `none()`, `in_bulk()`,
  `__contains__`, richer `__repr__`, `on_delete` (CASCADE/SET NULL/RESTRICT/
  PROTECT), transaction **savepoints** for nested `atomic()`.

### Added — CLI
- `endo new`, `endo routes`, `endo check`, `endo doctor`,
  `endo makemigrations` / `endo migrate` / `endo rollback`.

### Fixed
- `__eq__` for unsaved instances (identity), `bulk_create` now backfills pks on
  SQLite, `values_list()` returns **tuples** (was dicts).
- **SQLite `LIKE` made case-sensitive** (`PRAGMA case_sensitive_like`) so
  `contains`/`icontains` behave identically to PostgreSQL.
- Column DDL emits `DEFAULT` for constant defaults (so `ADD COLUMN NOT NULL`
  works in migrations); SQLite `check_same_thread=False` + a connection lock.

## [0.3.0b1] — 2026-05-02 — third Beta: ORM completeness, encrypted files, deferrals

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
  `endo dev --default-version latest` resolves a version-less path to the newest
  version and logs which one served it (strict 404 stays the default).
- **Request streaming** (`Request.stream()`) and `StreamingResponse`.
- **In-process dev watcher** (`watchfiles`) rebuilds the route tree on change
  without a process restart (`Application.reload()`).
- **`endo test`** now passes pytest flags directly (`endo test -q -k name`).

### Changed
- Optional extras: `endocore[files]` (cryptography), `endocore[watch]`.
- Version -> 0.3.0b1. 102 tests total.

## [0.2.0b1] — 2026-04-17 — second Beta: the ORM

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

## [0.1.0b1] — 2026-04-08 — first Beta

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
- **CLI `endo`** — `create`, `dev` (uvicorn + reload), `version create`/`list`,
  `test`. `version create` copies endpoints + local services (never global
  `Services/`) and rewrites `Api.vSRC` → `Api.vDEST` imports so a new version
  uses its own local services (real isolation).
- **Framework test suite** (`tests/`, 29 tests) and a runnable `example/` app.

### Known limitations
- `endo test` needs `--` before pytest flags: `endo test -- -q -k name`.
- No default-to-latest version alias, no request-body streaming, no
  `pydantic` validation, no custom `watchfiles` watcher (uses uvicorn reload).
  These are intentionally deferred.
