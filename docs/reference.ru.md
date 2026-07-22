# Справочник API

Сжатая карта публичного API. Поверхность фреймворка импортируется из
`endocore`, ORM — из `endocore.orm`.

## `endocore`

**Ядро**

- `Application(app_dir=".", *, dev=False, default_version=None, max_body_size=…, openapi=None, openapi_title=…)` — `openapi=None`: `/docs` + `/openapi.json` отдаются только при `dev=True`
- `Request` — `.method .path .path_params .query .headers .cookies`,
  `await .json() .body() .form() .files()`, `.stream()`, `.get_signed_cookie()`
- `Response(content, status=200, headers=None, media_type=…, background=None)` —
  `.json() .text() .redirect() .no_content()`, `.set_cookie() .set_signed_cookie() .delete_cookie()`
- `StreamingResponse(content, …)`
- `WebSocket`, `WebSocketDisconnect`, `WebSocketManager`
- `get_logger()`

**Внедрение зависимостей и конфигурация**

- `Depends(dependency)`
- `Settings`, `env(name, default=None, cast=None)`, `load_dotenv(path)`

**Кэш**

- `configure_cache(backend="memory"|"redis", …)`, `get_cache(alias="default")`, `cached(ttl=None, …)`

**HTTP-исключения**

- `HTTPError(status, detail)`, `BadRequest`, `Unauthorized`, `Forbidden`
  (`PermissionDenied`), `NotFound`, `MethodNotAllowed`, `Conflict`,
  `PayloadTooLarge`, `UnprocessableEntity`, `TooManyRequests`

**Структуры данных**

- `QueryParams`, `FormData`, `UploadFile`

**Auth и пароли**

- `login(request, pk)`, `logout(request)`, `user_id(request)`,
  `require_user_id(request)` — DI-dependency (401 for anonymous)
- `hash_password(pw)`, `verify_password(pw, stored)`, `needs_rehash(stored)`

## `endocore.middleware`

- `logging_middleware`
- `cors_middleware(...)`, `security_headers_middleware(...)`, `gzip_middleware(...)`,
  `proxy_headers_middleware(...)`, `rate_limit_middleware(...)`,
  `timeout_middleware(...)`, `csrf_middleware(secret)`,
  `session_middleware(secret, cookie_name="session", max_age=…, secure=False)`

## `endocore.orm`

**Модели и поля**

- `Model`, `fields.*` (см. [Поля](orm/fields.md)), `get_models()`

**Соединения и схема**

- `configure(backend=…, alias="default", pool_size=…, **params)`, `connect(...)`,
  `get_connection(alias)`, `atomic(alias="default")`, `aatomic(alias="default")`, `close_all()`
- `create_all(*models)`, `create_table(model)`, `create_through_tables(model)`, `drop_table(model)`

**Запросы**

- `Model.objects` (Manager) → QuerySet
- `Q`, `F`, `Count`, `Sum`, `Avg`, `Min`, `Max`
- QuerySet: `filter exclude get first last count exists all none order_by
  values values_list distinct only defer annotate select_related prefetch_related
  create bulk_create update bulk_update delete get_or_create update_or_create
  in_bulk aggregate earliest latest`
- Async-близнецы: `aget acreate acount aexists afirst alast alist aupdate adelete
  abulk_create abulk_update aaggregate aget_or_create` + `async for`

**Миграции**

- `Migrator(models=None, using="default", directory="migrations")` —
  `makemigrations(name, renames=None) migrate(target=None) rollback(steps=1)
  showmigrations() sqlmigrate(name)`

**Файлы и хранилище**

- `fields.FileField(upload_to=…, storage=None)`
- `configure_storage(root, key=…)`, `generate_key()`, `get_storage()`,
  `EncryptedFileSystemStorage`, `StorageError`

**Исключения**

- `ORMError`, `ConfigurationError`, `UnsafeIdentifierError`, `FieldError`,
  `DoesNotExist`, `MultipleObjectsReturned`, `ValidationError`

## `endocore.extensions`

- `Extension` (база), `RedisExtension`, `CeleryExtension`, `EmailExtension`,
  `CacheExtension`, `redis_client(...)`, `celery_app(...)`, `EmailClient`

---

!!! tip "Самый глубокий справочник — исходники"
    EndoCore маленький и читаемый. Сомневаетесь — читайте модуль: у каждой
    публичной функции есть docstring, а пакет задуман так, чтобы его можно было
    понять целиком.
