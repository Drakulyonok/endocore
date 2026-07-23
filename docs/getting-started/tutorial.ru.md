# Туториал: небольшой API блога

Мы соберём версионированный API блога с моделями, тонкими endpoint'ами,
сервисным слоем, middleware, миграциями и тестами — так, как устроен настоящий
проект на EndoCore.

К концу у вас будет `v1`, отдающий посты и комментарии, auth-middleware и `v2`,
меняющий контракт, не трогая `v1`.

## 0. Подготовка

```bash
endo new blog && cd blog
pip install "endocore[pydantic]"
```

## 1. Модели

Модели живут в `Models/` и настраивают базу данных при импорте.

```python
# Models/blog.py
from endocore.orm import Model, fields, configure, create_all

configure(backend="sqlite", database="blog.db")   # или backend="postgres", ...

class Author(Model):
    class Meta:
        ordering = ["name"]
    name  = fields.CharField(max_length=100, unique=True)
    email = fields.EmailField()

class Post(Model):
    class Meta:
        ordering = ["-id"]
    title   = fields.CharField(max_length=200)
    body    = fields.TextField(default="")
    views   = fields.IntegerField(default=0)
    author  = fields.ForeignKey(Author, related_name="posts")
    created = fields.DateTimeField(auto_now_add=True)

class Comment(Model):
    post = fields.ForeignKey(Post, related_name="comments")
    text = fields.TextField()

create_all(Author, Post, Comment)
```

!!! tip "Миграции вместо `create_all`"
    `create_all` отлично подходит для прототипов. В реальном проекте используйте
    [миграции](../orm/migrations.md): `endo makemigrations && endo migrate`.

## 2. Сервисный слой

Держите endpoint'ы **тонкими** — распарсить вход, вызвать сервис, вернуть ответ.
Бизнес-логику кладите в сервисы, чтобы новая версия API могла её переиспользовать.

```python
# Services/posts.py
from Models.blog import Author, Post

def create_post(*, author_name: str, title: str, body: str = "") -> Post:
    author, _ = Author.objects.get_or_create(
        name=author_name, defaults={"email": f"{author_name}@example.com"}
    )
    return Post.objects.create(author=author, title=title, body=body)

def list_posts(limit: int = 20):
    return list(Post.objects.select_related("author")[:limit])
```

## 3. Endpoint'ы (тонкие)

```python
# Api/v1/Post/Get.py   (GET /v1/post)
from endocore import Request, Response
from Services.posts import list_posts

async def handler(request: Request) -> Response:
    posts = list_posts(limit=int(request.query.get("limit", "20")))
    return Response.json({"posts": [
        {"id": p.pk, "title": p.title, "author": p.author.name} for p in posts
    ]})
```

```python
# Api/v1/Post/Post.py   (POST /v1/post)
from endocore import Request, Response
from pydantic import BaseModel
from Services.posts import create_post

class PostIn(BaseModel):
    author: str
    title: str
    body: str = ""

async def handler(request: Request, data: PostIn) -> Response:   # (1)
    post = create_post(author_name=data.author, title=data.title, body=data.body)
    return Response.json({"id": post.pk, "title": post.title}, status=201)
```

1. Поскольку `data` аннотирован pydantic-моделью, EndoCore валидирует JSON-тело
   в неё и при ошибке возвращает **422** с ошибками по полям. Схема также
   попадает в `/docs`.

## 4. Динамические сегменты и связи

```python
# Api/v1/Post/[id]/Get.py   (GET /v1/post/42)
from endocore import Request, Response, NotFound
from Models.blog import Post

async def handler(request: Request) -> Response:
    try:
        post = Post.objects.select_related("author").get(pk=request.path_params["id"])
    except Post.DoesNotExist:
        raise NotFound("post not found")
    comments = list(post.comments.all())          # обратный FK
    return Response.json({
        "id": post.pk, "title": post.title, "author": post.author.name,
        "comments": [c.text for c in comments],
    })
```

## 5. Middleware

Middleware регистрируются в `Middleware/__init__.py`. Здесь мы добавим CORS,
security-заголовки и простую токен-авторизацию для методов записи.

```python
# Middleware/auth.py
from endocore import Request, Response, Unauthorized

async def auth_middleware(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        if request.headers.get("authorization") != "Bearer secret":
            raise Unauthorized("missing or invalid token")
    return await call_next(request)
```

```python
# Middleware/__init__.py
from endocore.middleware import cors_middleware, security_headers_middleware
from Middleware.auth import auth_middleware

middlewares = [
    cors_middleware(allow_origins=["*"]),
    security_headers_middleware(),
    auth_middleware,      # первый = самый внешний (после логирования фреймворка)
]
```

## 6. Внедрение зависимостей

Нужен пул БД, объект настроек или текущий пользователь во многих обработчиках?
Объявите зависимость — EndoCore соберёт её сам.

```python
# providers.py
from Services.settings import get_settings
providers = {"settings": get_settings}
```

```python
# Api/v1/Config/Get.py
from endocore import Response, Depends
from Services.settings import get_settings

async def handler(request, settings = Depends(get_settings)) -> Response:
    return Response.json({"debug": settings.debug})
```

## 7. Версионирование

Вы поменяли контракт ответа и не хотите ломать существующих клиентов.
Скопируйте версию целиком:

```bash
endo version create 2        # Api/v1 -> Api/v2 (endpoint'ы + локальные сервисы)
```

Теперь свободно редактируйте `Api/v2/Post/Get.py`. `v1` продолжает вести себя
**в точности** как раньше — это и есть гарантия. См.
[Версионирование](../guide/versioning.md).

## 8. Миграции

```bash
endo makemigrations initial
endo migrate
# позже, после изменения моделей:
endo makemigrations add_views
endo migrate
endo showmigrations          # [x] применена  /  [ ] ожидает
endo rollback                # откатить последнюю
```

## 9. Тесты

Тесты живут в `Tests/` — это обычный `pytest`.

```python
# Tests/test_posts.py
from Services.posts import create_post
from Models.blog import Author, Comment, Post
from endocore.orm import configure, create_all

def setup_module():
    configure(backend="sqlite", database=":memory:")   # своя БД на каждый прогон
    create_all(Author, Post, Comment)

def test_create_post():
    post = create_post(author_name="Ada", title="Hello")
    assert Post.objects.filter(title="Hello").count() == 1
```

Запуск:

```bash
endo test -q
```

## 10. Запуск

```bash
endo dev                     # dev-режим с перезагрузкой в процессе
# продакшен:
uvicorn endocore.asgi:create_app --factory --host 0.0.0.0 --port 8000
```

Это готовый, слоёный, версионированный API. Продолжайте с разделами
[Руководство](../guide/architecture.md) и [ORM](../orm/index.md).
