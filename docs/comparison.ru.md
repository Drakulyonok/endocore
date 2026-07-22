# EndoCore vs FastAPI

Оба — современные Python ASGI-фреймворки, просто ставки у них разные.

## Коротко

| | EndoCore | FastAPI |
|---|---|---|
| Роутинг | Файловый: папка = путь, файл = метод | Декораторы (`@app.get(...)`) |
| Источник истины | Дерево каталога `Api/` | Python-код + декораторы |
| Версионирование | Встроено: папки `vN` сосуществуют | Вручную (роутеры/префиксы) |
| ORM | Встроенная, sync + async | Нет (SQLAlchemy/Tortoise) |
| Миграции | Встроенные (`end migrate`, rollback) | Alembic (отдельно) |
| CLI | Встроенный (`end`) | Нет (только uvicorn) |
| Валидация | pydantic, опционально по параметру | pydantic везде (в ядре) |
| DI | `Depends` + провайдеры по типу/имени | `Depends` |
| WebSockets | Файловый `Socket.py` + pub/sub | `@app.websocket` |
| Зависимости ядра | 1 (`uvicorn`) | Starlette + pydantic + typing-extensions |
| UI документации | `/docs` (Swagger) | `/docs` + `/redoc` |

## Берите EndoCore, если

- хотите, чтобы дерево папок и было контрактом API — коду и маршрутам просто
  негде разойтись;
- нужно версионирование, при котором новая версия не может сломать старую;
- удобнее получить ORM, миграции, кэш, DI, WebSockets и CLI из одного пакета;
- хотите кодовую базу, которую реально прочитать целиком.

## Берите FastAPI, если

- нужна самая большая экосистема и сообщество;
- вам привычно работать с pydantic-моделями везде;
- предпочитаете роутинг декораторами и свою ORM на выбор.

## Одна задача, оба способа

**FastAPI**

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class UserIn(BaseModel):
    name: str

@app.post("/v1/user")
async def create_user(data: UserIn):
    return {"created": data.name}
```

**EndoCore** — маршрут и есть файл `Api/v1/User/Post.py`:

```python
from endocore import Request, Response
from pydantic import BaseModel

class UserIn(BaseModel):
    name: str

async def handler(request: Request, data: UserIn) -> Response:
    return Response.json({"created": data.name}, status=201)
```

Та же валидация, тот же OpenAPI. Разница в том, где живёт маршрут: в EndoCore
URL и метод — это расположение и имя файла, `end routes` печатает дерево, а
новая версия API — копия папки.

## Производительность

На чистом диспатче внутри процесса EndoCore быстрее — примерно в 2.2 раза на
статическом маршруте и в 3.6 на динамическом — просто потому, что делает меньше
работы на запрос. Метод и оговорки — в [Бенчмарках](benchmarks.md). В реальном
приложении всё равно всё упирается в базу данных.

## Полезно знать

- Для валидации тел нужна экстра `pydantic`. С ней параметр обработчика с
  аннотацией `BaseModel` валидируется из JSON-тела: 422 при ошибке, схема в
  `/docs`. См. [Внедрение зависимостей](guide/dependency-injection.md).
- Асинхронная ORM — это синхронный движок в тредпуле. Используйте `a*`-методы
  (`aget`, `alist`, `asave`, …) — и event loop останется свободным. См.
  [Async ORM](orm/async.md).

FastAPI — отличный фреймворк. EndoCore — для тех, кому нравится идея дерева
папок и батарейки в комплекте.
