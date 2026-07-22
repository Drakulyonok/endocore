# Внедрение зависимостей

Внедрение зависимостей (DI) — это способ получить в обработчике готовые
объекты — пул базы данных, настройки, текущего пользователя — не создавая их в
каждом файле. Вы добавляете параметр в обработчик, EndoCore подставляет
значение.

Работает как в FastAPI: `Depends(...)` плюс провайдеры уровня приложения.

## `Depends`

```python
from endocore import Request, Response, Depends

async def db():
    return get_pool()                     # зависимость (sync или async)

async def current_user(request: Request, pool = Depends(db)):
    token = request.headers.get("authorization")
    return await pool.user_from(token)

async def handler(request: Request, user = Depends(current_user)):
    return Response.json({"user": user})
```

Зависимости могут зависеть от других зависимостей (вложенность) и
**кэшируются на запрос** — зависимость, использованная дважды, выполнится один
раз.

## Порядок разрешения

Для каждого параметра обработчика, по порядку:

1. `request` (по имени или аннотации `Request`) → объект Request.
2. `websocket` (по имени или аннотации `WebSocket`) → объект WebSocket.
3. Значение по умолчанию — `Depends(fn)` → разрешить `fn`.
4. Имя совпадает с захваченным **path-параметром** (`[id]`) → это значение.
5. **Провайдер** уровня приложения для аннотации (типа) или имени.
6. Аннотация — **pydantic-модель** → валидируется из JSON-тела (см. ниже).
7. Собственное значение по умолчанию параметра, если есть.
8. Иначе → `DIError`.

## Провайдеры уровня приложения

Зарегистрируйте синглтоны/сервисы один раз; инжектируйте по **имени** или
**типу**:

```python
# providers.py
from Services.db import make_pool
from Services.settings import Settings, get_settings

providers = {
    "db": make_pool,          # инжект параметра с именем `db`
    Settings: get_settings,   # инжект параметра с аннотацией `Settings`
}
```

```python
async def handler(request, db, settings: Settings):
    ...
```

Провайдеры — **синглтоны по умолчанию** (создаются один раз, переиспользуются).
Можно регистрировать и в рантайме: `app.provide("db", make_pool, singleton=True)`.

## Pydantic-тела

С `endocore[pydantic]` параметр, аннотированный `BaseModel`, валидируется из
JSON-тела — при ошибке **422** с ошибками по полям, а схема появляется в
`/docs`:

```python
from pydantic import BaseModel

class UserIn(BaseModel):
    name: str
    age: int

async def handler(request, data: UserIn):    # POST-тело -> валидированный UserIn
    return Response.json({"name": data.name}, status=201)
```

## Производительность

Типичная сигнатура `handler(request)` идёт по **быстрому пути**, полностью
минуя разрешение зависимостей. Сигнатуры и type-хинты кэшируются, так что для
обычных обработчиков накладные расходы DI ничтожны.
