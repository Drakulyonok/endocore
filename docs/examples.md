# Example projects

The repository ships a runnable **`example/`** app and these blueprints show how
to lay out larger projects. Each is just a folder tree — that's the point.

## 1. Bundled example (`example/`)

```bash
git clone https://github.com/Drakulyonok/endocore
cd endocore/example
endo dev            # http://127.0.0.1:8000
```

It demonstrates: versioned routes, dynamic segments, local vs global services,
an ORM-backed `Post` model, request-id middleware, an encrypted-file demo, and a
`ws /v1/chat` echo socket.

## 2. A REST API with auth & the ORM

```text
blog/
  Api/
    v1/
      Auth/
        Post.py            # POST /v1/auth  (login -> signed cookie)
      Post/
        Get.py             # GET  /v1/post  (list, paginated)
        Post.py            # POST /v1/post  (create; pydantic body)
        [id]/
          Get.py           # GET  /v1/post/42
          Delete.py        # DELETE /v1/post/42  (auth required)
  Middleware/
    __init__.py            # cors + security headers + auth
    auth.py
  Models/
    blog.py                # Author, Post, Comment
  Services/
    posts.py               # business logic
  hooks.py                 # open/close resources
  providers.py             # DI providers (settings, db)
  migrations/              # endo makemigrations / migrate
  Tests/
    test_posts.py
```

Key ideas:

- Endpoints are thin; logic lives in `Services/posts.py`.
- Auth is a middleware for writes; `current_user` is a DI dependency for reads.
- Models evolve through migrations, not `create_all`.

## 3. Real-time app (WebSockets + pub/sub)

```text
chat/
  Api/
    v1/
      Rooms/
        [room]/
          Socket.py        # ws /v1/rooms/<room> — join, broadcast
      Rooms/
        Get.py             # GET /v1/rooms — active rooms
  Services/
    presence.py            # a shared WebSocketManager
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

## 4. Background jobs with Redis + Celery

```text
worker_app/
  extensions.py            # RedisExtension + CacheExtension
  Services/
    tasks.py               # celery_app + @app.task
  Api/
    v1/
      Jobs/
        Post.py            # enqueue a task -> 202
```

See [Celery](extensions/celery.md) and [Redis](extensions/redis.md).

---

Want your project listed here? Open a PR — see [Contributing](contributing.md).
