# Рецепты

Короткие, готовые к копированию рецепты для типовых задач.

## Middleware токен-авторизации

```python
# Middleware/auth.py
from endocore import Request, Unauthorized

async def auth_middleware(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        token = request.headers.get("authorization", "")
        if token != "Bearer secret":
            raise Unauthorized("invalid token")
    return await call_next(request)
```

## Текущий пользователь через DI

```python
# Services/auth.py
from endocore import Request, Unauthorized

async def current_user(request: Request):
    token = request.headers.get("authorization", "").removeprefix("Bearer ")
    user = User.objects.filter(token=token).first()
    if user is None:
        raise Unauthorized()
    return user
```

```python
# Api/v1/Me/Get.py
from endocore import Response, Depends
from Services.auth import current_user

async def handler(request, user = Depends(current_user)):
    return Response.json({"id": user.pk, "name": user.name})
```

## Пагинация

```python
async def handler(request):
    page = max(1, int(request.query.get("page", "1")))
    size = min(100, int(request.query.get("size", "20")))
    qs = Post.objects.order_by("-id")
    items = list(qs[(page - 1) * size : page * size])
    return Response.json({
        "page": page, "size": size, "total": qs.count(),
        "items": [{"id": p.pk, "title": p.title} for p in items],
    })
```

## Загрузка файла

```python
# Api/v1/Upload/Post.py
from endocore import Response, HTTPError
from Models.docs import Document

async def handler(request):
    files = await request.files()
    upload = files.get("file")
    if upload is None:
        raise HTTPError(422, "no file")
    doc = Document.objects.create(name=upload.filename, file=upload.read())  # шифруется
    return Response.json({"id": doc.pk}, status=201)
```

## Установка и чтение подписанной сессионной cookie

```python
# логин
resp = Response.json({"ok": True})
resp.set_signed_cookie("session", str(user.id), secret=SECRET, httponly=True, max_age=86400)
return resp
```

```python
# защищённый маршрут
uid = request.get_signed_cookie("session", secret=SECRET, max_age=86400)
if uid is None:
    raise Unauthorized()
```

## Публичный endpoint с rate limit

```python
# Middleware/__init__.py
from endocore.middleware import rate_limit_middleware
middlewares = [rate_limit_middleware(limit=60, window=60)]   # 60 req/мин на IP
```

## Кэширование дорогого запроса

```python
from endocore import cached

@cached(ttl=30)
def top_posts():
    return list(Post.objects.order_by("-views")[:10])
```

## Чат-комната на WebSocket

```python
# Api/v1/Chat/Socket.py
from endocore import WebSocket, WebSocketManager

room = WebSocketManager()

async def handler(websocket: WebSocket):
    await room.connect(websocket, room="global")
    try:
        async for msg in websocket.iter_text():
            await room.broadcast(msg, room="global")
    finally:
        room.disconnect(websocket)
```

## Health check + версия

```python
# Api/v1/Health/Get.py
from endocore import Response, __version__

async def handler(request):
    return Response.json({"status": "ok", "version": __version__})
```

## Асинхронная БД в обработчике

```python
async def handler(request):
    posts = await Post.objects.order_by("-id").alist()
    return Response.json({"posts": [p.title for p in posts]})
```

## CORS для SPA

```python
from endocore.middleware import cors_middleware
middlewares = [cors_middleware(
    allow_origins=["https://app.example.com"],
    allow_credentials=True,
)]
```
