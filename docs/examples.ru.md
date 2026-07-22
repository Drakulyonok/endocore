# Примеры проектов

В репозитории есть запускаемое приложение **`example/`**, а эти блюпринты
показывают, как раскладывать более крупные проекты. Каждый — просто дерево
папок; в этом и суть.

## 1. Пример из репозитория (`example/`)

```bash
git clone https://github.com/Drakulyonok/endocore
cd endocore/example
end dev            # http://127.0.0.1:8000
```

Он демонстрирует: версионированные маршруты, динамические сегменты, локальные и
глобальные сервисы, модель `Post` на ORM, middleware с request-id, демо
шифрованных файлов и echo-сокет `ws /v1/chat`.

## 2. REST API с авторизацией и ORM

```text
blog/
  Api/
    v1/
      Auth/
        Post.py            # POST /v1/auth  (логин -> подписанная cookie)
      Post/
        Get.py             # GET  /v1/post  (список, с пагинацией)
        Post.py            # POST /v1/post  (создание; pydantic-тело)
        [id]/
          Get.py           # GET  /v1/post/42
          Delete.py        # DELETE /v1/post/42  (нужна авторизация)
  Middleware/
    __init__.py            # cors + security headers + auth
    auth.py
  Models/
    blog.py                # Author, Post, Comment
  Services/
    posts.py               # бизнес-логика
  hooks.py                 # открытие/закрытие ресурсов
  providers.py             # DI-провайдеры (settings, db)
  migrations/              # end makemigrations / migrate
  Tests/
    test_posts.py
```

Ключевые идеи:

- Endpoint'ы тонкие; логика живёт в `Services/posts.py`.
- Авторизация — middleware для записи; `current_user` — DI-зависимость для чтения.
- Модели развиваются через миграции, а не `create_all`.

## 3. Real-time приложение (WebSockets + pub/sub)

```text
chat/
  Api/
    v1/
      Rooms/
        [room]/
          Socket.py        # ws /v1/rooms/<room> — вход, broadcast
      Rooms/
        Get.py             # GET /v1/rooms — активные комнаты
  Services/
    presence.py            # общий WebSocketManager
```

```python
# Services/presence.py
from endocore import WebSocketManager
manager = WebSocketManager()
```

```python
# Api/v1/Rooms/[room]/Socket.py
from endocore import WebSocket
from Services.presence import manager

async def handler(websocket: WebSocket):
    room = websocket.path_params["room"]
    await manager.connect(websocket, room=room)
    try:
        async for msg in websocket.iter_text():
            await manager.broadcast(msg, room=room, exclude=websocket)
    finally:
        manager.disconnect(websocket)
```

## 4. Фоновые задачи с Redis + Celery

```text
worker_app/
  extensions.py            # RedisExtension + CacheExtension
  Services/
    tasks.py               # celery_app + @app.task
  Api/
    v1/
      Jobs/
        Post.py            # поставить задачу в очередь -> 202
```

См. [Celery](extensions/celery.md) и [Redis](extensions/redis.md).

---

Хотите увидеть здесь свой проект? Откройте PR — см.
[Участие в проекте](contributing.md).
