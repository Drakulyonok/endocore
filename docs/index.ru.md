# EndoCore

**Файловый ASGI backend-фреймворк — дерево папок *является* API.**

Никаких роутеров, декораторов и конфигов регистрации. Положил файл в нужную
папку — endpoint появился. Роутинг, версионирование и CLI — это просто
**операции над одним деревом каталогов**.

<p align="center">
  <em>Чистый ASGI · одна зависимость ядра (<code>uvicorn</code>) · безопасная ORM ·
  DI · WebSockets · кэш · OpenAPI · миграции · 1600+ тестов.</em>
</p>

<p align="center" markdown>
[Начать](getting-started/quickstart.md){ .md-button .md-button--primary }
[Туториал](getting-started/tutorial.md){ .md-button }
[vs FastAPI](comparison.md){ .md-button }
[Discord](https://discord.gg/jwvGj2M9EX){ .md-button }
</p>

---

## Идея за десять секунд

```text
Api/
  v1/
    User/
      Role/
        Get.py      # GET  /v1/user/role
        Post.py     # POST /v1/user/role
      [id]/
        Get.py      # GET  /v1/user/42   ->  id = "42"
```

```python
# Api/v1/User/Role/Get.py
from endocore import Request, Response

async def handler(request: Request) -> Response:
    return Response.json({"roles": ["admin", "editor", "viewer"]})
```

```bash
end dev            # http://127.0.0.1:8000
```

Папка — это URL, имя файла — HTTP-метод, `[id]` захватывает значение, а первая
папка `vN` — версия API. Это вся модель роутинга.

---

## Почему EndoCore

<div class="grid cards" markdown>

-   :material-file-tree: **Файл = маршрут**

    Структура и есть API. Что видно в дереве — ровно то и отдаёт сервер. Ни
    скрытой регистрации, ни расхождения между кодом и маршрутами.

-   :material-database-lock: **Безопасная ORM (SQLite + PostgreSQL)**

    В стиле Django, но с приоритетом безопасности: любое значение биндится
    драйвером, идентификаторы валидируются и квотируются, операторы — из белого
    списка. Готова к async.

-   :material-needle: **Внедрение зависимостей**

    `Depends(...)` как в FastAPI плюс провайдеры уровня приложения — вложенные,
    кэшируются на запрос, резолвятся по типу или имени.

-   :material-lightning-bolt: **Батарейки в комплекте**

    WebSockets + pub/sub, кэш (память/Redis), middleware CORS/CSRF/gzip/rate-limit,
    cookies, фоновые задачи, миграции с откатом, OpenAPI.

</div>

---

## Немного об ORM

```python
from endocore.orm import Model, fields, configure, create_all, Count

class Author(Model):
    name = fields.CharField(max_length=100)

class Book(Model):
    title  = fields.CharField(max_length=200)
    author = fields.ForeignKey(Author, related_name="books")

configure(backend="sqlite", database="app.db")
create_all(Author, Book)

Author.objects.create(name="Ada")
Book.objects.filter(author__name="Ada")             # кросс-табличный lookup (JOIN)
Author.objects.annotate(n=Count("books"))           # агрегат по связи
await Book.objects.aget(id=1)                        # async (неблокирующий)
```

---

## Установка

```bash
pip install endocore
# экстры: pip install "endocore[postgres,files,redis,pydantic]"
```

Первый раз здесь? Идите по порядку:

1. [Установка](getting-started/installation.md) — один `pip install`.
2. [Быстрый старт](getting-started/quickstart.md) — рабочий API за минуту.
3. [Туториал](getting-started/tutorial.md) — небольшой API блога целиком:
   модели, сервисы, middleware, версии, тесты.

---

## Статус

EndoCore — бета (`0.7.0b1`), стабилизируется к `1.0`. Поставляется с 1600+
тестами, покрывающими роутинг, ORM (оба диалекта, тесты на инъекции), миграции,
middleware, DI, кэш и WebSockets.

!!! note "Одна зависимость ядра"
    Ядро зависит от одного внешнего пакета: `uvicorn`. Резолвер,
    Request/Response, middleware, CLI и ORM написаны на стандартной библиотеке.
    PostgreSQL, шифрование файлов, Redis, Celery и pydantic — опциональные
    extras. Подробнее — в [Философии](getting-started/philosophy.md).
