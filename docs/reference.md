# API Reference

A concise map of the public API. Import the framework surface from `endocore`
and the ORM from `endocore.orm`.

## `endocore`

**Core**

- `Application(app_dir=".", *, dev=False, default_version=None, max_body_size=…, openapi=True, openapi_title=…)`
- `Request` — `.method .path .path_params .query .headers .cookies`,
  `await .json() .body() .form() .files()`, `.stream()`, `.get_signed_cookie()`
- `Response(content, status=200, headers=None, media_type=…, background=None)` —
  `.json() .text() .redirect() .no_content()`, `.set_cookie() .set_signed_cookie() .delete_cookie()`
- `StreamingResponse(content, …)`
- `WebSocket`, `WebSocketDisconnect`, `WebSocketManager`
- `get_logger()`

**Dependency injection & config**

- `Depends(dependency)`
- `Settings`, `env(name, default=None, cast=None)`, `load_dotenv(path)`

**Cache**

- `configure_cache(backend="memory"|"redis", …)`, `get_cache(alias="default")`, `cached(ttl=None, …)`

**HTTP exceptions**

- `HTTPError(status, detail)`, `BadRequest`, `Unauthorized`, `Forbidden`
  (`PermissionDenied`), `NotFound`, `MethodNotAllowed`, `Conflict`,
  `PayloadTooLarge`, `UnprocessableEntity`, `TooManyRequests`

**Data structures**

- `QueryParams`, `FormData`, `UploadFile`

## `endocore.middleware`

- `logging_middleware`
- `cors_middleware(...)`, `security_headers_middleware(...)`, `gzip_middleware(...)`,
  `proxy_headers_middleware(...)`, `rate_limit_middleware(...)`,
  `timeout_middleware(...)`, `csrf_middleware(secret)`

## `endocore.orm`

**Models & fields**

- `Model`, `fields.*` (see [Fields](orm/fields.md)), `get_models()`

**Connections & schema**

- `configure(backend=…, alias="default", **params)`, `connect(...)`,
  `get_connection(alias)`, `atomic(alias="default")`, `close_all()`
- `create_all(*models)`, `create_table(model)`, `create_through_tables(model)`, `drop_table(model)`

**Queries**

- `Model.objects` (Manager) → QuerySet
- `Q`, `F`, `Count`, `Sum`, `Avg`, `Min`, `Max`
- QuerySet: `filter exclude get first last count exists all none order_by
  values values_list distinct only defer annotate select_related prefetch_related
  create bulk_create update bulk_update delete get_or_create update_or_create
  in_bulk aggregate earliest latest`
- Async twins: `aget acreate acount aexists afirst alast alist aupdate adelete
  abulk_create abulk_update aaggregate aget_or_create` + `async for`

**Migrations**

- `Migrator(models=None, using="default", directory="migrations")` —
  `makemigrations(name, renames=None) migrate(target=None) rollback(steps=1)
  showmigrations() sqlmigrate(name)`

**Files & storage**

- `fields.FileField(upload_to=…, storage=None)`
- `configure_storage(root, key=…)`, `generate_key()`, `get_storage()`,
  `EncryptedFileSystemStorage`, `StorageError`

**Exceptions**

- `ORMError`, `ConfigurationError`, `UnsafeIdentifierError`, `FieldError`,
  `DoesNotExist`, `MultipleObjectsReturned`, `ValidationError`

## `endocore.extensions`

- `Extension` (base), `RedisExtension`, `CeleryExtension`, `EmailExtension`,
  `CacheExtension`, `redis_client(...)`, `celery_app(...)`, `EmailClient`

---

!!! tip "Source is the deepest reference"
    EndoCore is small and readable. When in doubt, read the module — every public
    function has a docstring, and the package is designed to be understood
    end-to-end.
