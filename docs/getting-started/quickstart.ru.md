# Быстрый старт

Рабочий API примерно за минуту.

## 1. Сгенерируйте проект

```bash
end new blog
cd blog
```

Готовая структура:

```text
blog/
  Api/
    v1/
      Health/
        Get.py          # GET /v1/health
  Middleware/
    __init__.py         # здесь регистрируется middleware
  Services/  Models/  Utils/  Tests/
  hooks.py              # хуки startup / shutdown
  extensions.py         # интеграции сервисов (Redis, кэш, ...)
```

## 2. Запустите dev-сервер

```bash
end dev            # http://127.0.0.1:8000
```

Откройте `http://127.0.0.1:8000/v1/health` → `{"status": "ok"}`.
А `http://127.0.0.1:8000/docs` — интерактивный **Swagger UI**.

## 3. Добавьте endpoint

Сгенерируйте:

```bash
end create user/profile get
# -> Api/v1/User/Profile/Get.py   (GET /v1/user/profile)
```

…или просто создайте файл. **Папка — это путь, имя файла — это метод.**

```python
# Api/v1/User/Profile/Get.py
from endocore import Request, Response

async def handler(request: Request) -> Response:
    return Response.json({"name": "Ada", "role": "admin"})
```

Dev-watcher пересобирает дерево маршрутов в процессе — без рестарта.

## 4. Динамические сегменты

Папка с именем `[id]` захватывает параметр пути:

```python
# Api/v1/User/[id]/Get.py
from endocore import Request, Response

async def handler(request: Request) -> Response:
    user_id = request.path_params["id"]         # "42" для /v1/user/42
    return Response.json({"id": user_id})
```

## 5. Чтение входных данных

```python
# Api/v1/User/Post.py   (POST /v1/user)
from endocore import Request, Response, HTTPError

async def handler(request: Request) -> Response:
    data = await request.json()
    if not data.get("name"):
        raise HTTPError(422, "name is required")
    return Response.json({"created": data["name"]}, status=201)
```

Также доступны `request.query`, `request.headers`, `request.cookies`,
`await request.form()` / `await request.files()`.

## 6. Подключите ORM

```python
# Models/blog.py
from endocore.orm import Model, fields, configure, create_all

configure(backend="sqlite", database="blog.db")

class Post(Model):
    title = fields.CharField(max_length=200)
    body  = fields.TextField(default="")

create_all(Post)
```

```python
# Api/v1/Post/Post.py   (POST /v1/post)
from endocore import Request, Response
from Models.blog import Post

async def handler(request: Request) -> Response:
    data = await request.json()
    post = Post.objects.create(title=data["title"], body=data.get("body", ""))
    return Response.json({"id": post.pk, "title": post.title}, status=201)
```

## 7. Осмотрите приложение

```bash
end routes         # все маршруты + файл, в который они мапятся
end check          # битые хендлеры, дубли маршрутов
end openapi        # печать OpenAPI-схемы
```

Это весь цикл. Дальше — [Туториал](tutorial.md): соберём полноценный
версионированный API с сервисами, middleware и миграциями.
