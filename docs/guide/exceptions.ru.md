# Ошибки и исключения

Нужно ответить «404 Not Found» или «401 Unauthorized» из глубины кода? Бросьте
исключение — EndoCore поймает его в любом месте обработчика или middleware и
превратит в JSON-ответ с нужным статусом.

```python
from endocore import Request, Response, NotFound, Unauthorized

async def handler(request: Request) -> Response:
    user = find_user(request.path_params["id"])
    if user is None:
        raise NotFound("user not found")     # -> 404 {"error": "user not found"}
    if not user.active:
        raise Unauthorized()                 # -> 401 {"error": "Unauthorized"}
    return Response.json(user.to_dict())
```

## Встроенные исключения

Импортируются из `endocore`:

| Класс | Статус |
|-------|--------|
| `BadRequest` | 400 |
| `Unauthorized` | 401 |
| `Forbidden` (= `PermissionDenied`) | 403 |
| `NotFound` | 404 |
| `MethodNotAllowed` | 405 |
| `Conflict` | 409 |
| `PayloadTooLarge` | 413 |
| `UnprocessableEntity` | 422 |
| `TooManyRequests` | 429 |
| `HTTPError(status, detail)` | любой |

Каждое принимает опциональное сообщение; без него используется разумный
default (`NotFound()` → "Not Found").

```python
from endocore import HTTPError
raise HTTPError(418, "I'm a teapot")
```

## Как обрабатываются ошибки

Всегда включённый логирующий middleware:

- ловит любой `HTTPError` (из обработчика **или** любого middleware) и
  возвращает `{"error": detail}` с нужным статусом;
- ловит любое другое исключение, логирует трейсбэк (с замаскированным
  payload'ом и id запроса) и возвращает **500**;
- поэтому **один сломанный обработчик никогда не убивает соединение молча**.

Тело ответа для HTTP-исключения — `{"error": <detail>}`. Для ошибки валидации
pydantic (422) `detail` — это список записей `{"field", "message"}`.

## Ошибки на старте

Файл endpoint'а, который не смог **импортироваться**, не роняет приложение —
ошибка собирается и показывается в сводке при старте и в `end check`. Остальное
приложение продолжает работать.
