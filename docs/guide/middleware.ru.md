# Middleware

Middleware — это функция, через которую проходит каждый запрос до вашего
обработчика и каждый ответ после него. Сюда кладут то, что касается всех
endpoint'ов сразу: проверку авторизации, CORS, rate limit, замер времени.

Слои оборачивают обработчик как луковицу: каждый middleware получает `Request`
и `call_next` и либо возвращает ответ сразу, либо передаёт управление внутрь.

```python
from endocore import Request, Response

async def timing_middleware(request: Request, call_next):
    import time
    start = time.perf_counter()
    response = await call_next(request)          # внутрь
    ms = (time.perf_counter() - start) * 1000
    response.headers["X-Elapsed-ms"] = f"{ms:.1f}"
    return response
```

## Регистрация middleware

Перечислите их по порядку в `Middleware/__init__.py`. **Первый — самый внешний**
(сразу внутри логирующего middleware фреймворка).

```python
# Middleware/__init__.py
from endocore.middleware import cors_middleware, security_headers_middleware
from Middleware.auth import auth_middleware

middlewares = [
    cors_middleware(allow_origins=["https://app.example.com"]),
    security_headers_middleware(),
    auth_middleware,
]
```

## Ранний выход

Верните `Response` (или бросьте [HTTP-исключение](exceptions.md)), чтобы
остановиться до обработчика:

```python
from endocore import Request, Response, Unauthorized

async def auth_middleware(request: Request, call_next):
    if not request.headers.get("authorization"):
        raise Unauthorized("missing token")      # отрендерится как 401
    return await call_next(request)
```

## Middleware из коробки

Импортируются из `endocore.middleware`:

| Фабрика | Назначение |
|---------|---------|
| `cors_middleware(...)` | CORS-заголовки + preflight |
| `security_headers_middleware(...)` | `X-Content-Type-Options`, `X-Frame-Options`, HSTS, … |
| `gzip_middleware(...)` | gzip-сжатие больших ответов |
| `proxy_headers_middleware(...)` | учитывать `X-Forwarded-*` от доверенных прокси |
| `rate_limit_middleware(limit=, window=)` | rate limit в памяти с фиксированным окном (429) |
| `timeout_middleware(seconds=)` | прерывать медленные запросы с 504 |
| `csrf_middleware(secret)` | CSRF по схеме signed double-submit-cookie |

```python
from endocore.middleware import (
    cors_middleware, gzip_middleware, rate_limit_middleware, csrf_middleware,
)

middlewares = [
    cors_middleware(allow_origins=["*"]),
    gzip_middleware(minimum_size=500),
    rate_limit_middleware(limit=100, window=60),
    csrf_middleware(secret="change-me"),
]
```

## Всегда включённый логирующий слой

Собственный логирующий middleware фреймворка — всегда самый внешний слой. Он:

- замеряет и логирует каждый запрос (`[INFO] POST /v1/user/role 201 3ms id=…`),
- добавляет `X-Request-ID` (учитывая входящий),
- **маскирует чувствительные ключи** в логируемом payload'е,
- превращает любое брошенное [HTTP-исключение](exceptions.md) в его статус, а
  любое другое исключение — в 500 (с трейсбэком в логах).
