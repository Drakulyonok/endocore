# WebSockets

WebSocket держит соединение открытым, чтобы сервер мог отправлять сообщения
клиенту в любой момент — чаты, живые дашборды, уведомления.

В EndoCore они файловые, как и всё остальное: файл с именем **`Socket.py`**
(или `Ws.py`) в дереве Api — это websocket-endpoint.

```python
# Api/v1/Chat/Socket.py   ->  ws /v1/chat
from endocore import WebSocket

async def handler(websocket: WebSocket) -> None:
    await websocket.accept()
    async for message in websocket.iter_text():
        await websocket.send_text(f"echo: {message}")
```

Внедрение зависимостей работает и здесь (инжект `websocket`, path-параметров,
провайдеров, `Depends`).

## Объект WebSocket

```python
await websocket.accept(subprotocol=None)
msg  = await websocket.receive()          # сырое ASGI-сообщение
text = await websocket.receive_text()
data = await websocket.receive_json()
raw  = await websocket.receive_bytes()

await websocket.send_text("hi")
await websocket.send_json({"k": "v"})
await websocket.send_bytes(b"...")
await websocket.close(code=1000)

async for text in websocket.iter_text():  # пока клиент не отключится
    ...
async for obj in websocket.iter_json():
    ...

websocket.path, websocket.path_params, websocket.headers, websocket.query
```

Отключение клиента вызывает `WebSocketDisconnect`; хелперы `iter_*` корректно
останавливаются на нём. Несматченный websocket-путь отклоняется с кодом
закрытия `4404`.

## Проверка origin

Хендшейк по умолчанию требует совпадения origin вне `dev=True` — иначе
страница на любом другом сайте могла бы открыть websocket к вашему
приложению и прокатиться на cookie-сессии, поскольку браузер прикрепляет
cookies к websocket-хендшейку независимо от того, скрипт какого сайта открыл
соединение. Запрос без заголовка `Origin` (любой не-браузерный клиент) всегда
пропускается — там нет браузерной сессии, которую можно было бы угнать.

Отклонённые соединения закрываются с кодом `4403`. Настройте явно для
реального кросс-origin фронтенда:

```python
app = Application(ws_allowed_origins=["https://app.example.com"])
```

`ws_allowed_origins="*"` полностью отключает проверку; если не задавать
вовсе, она сама ослабляется в `dev=True` (локальный фронтенд на другом
порту — уже другой origin).

## Pub/Sub: комнаты и broadcast

`WebSocketManager` учитывает подключения по комнатам и рассылает сообщения:

```python
from endocore import WebSocket, WebSocketManager

chat = WebSocketManager()          # один общий менеджер (на уровне модуля)

# Api/v1/Chat/Socket.py
async def handler(websocket: WebSocket) -> None:
    await chat.connect(websocket, room="lobby")     # принимает + добавляет в комнату
    try:
        async for msg in websocket.iter_text():
            await chat.broadcast(msg, room="lobby") # отправить всем в комнате
    finally:
        chat.disconnect(websocket)
```

API менеджера:

```python
await chat.connect(ws, room="lobby")       # accept + войти в комнату
chat.add(ws, room="lobby")                 # добавить уже принятый сокет
chat.disconnect(ws, room="lobby")          # выйти (или из всех комнат при room=None)
await chat.broadcast("text", room="lobby", exclude=ws)
await chat.broadcast_json({"k": "v"}, room="lobby")
await chat.send_to(ws, "text")
chat.count("lobby"); chat.members("lobby"); chat.rooms_of(ws)
```

Мёртвые подключения автоматически удаляются при неудачной отправке.

### Рассылка между воркерами

По умолчанию комнаты живут в памяти, поэтому broadcast долетает только до
сокетов, которые держит *этот* процесс — запустите больше одного воркера, и
у каждого будет своя независимая копия каждой комнаты. Передайте
Redis-клиент, чтобы делить рассылку между всеми ними:

```python
from endocore.extensions import redis_client
from endocore import WebSocketManager

chat = WebSocketManager(redis_client=redis_client(url="redis://localhost:6379/0"))
```

Подключите жизненный цикл подписчика к хукам запуска/остановки приложения,
чтобы он начал слушать один раз и корректно остановился:

```python
# hooks.py
from Api.v1.Chat.Socket import chat

async def on_startup() -> None:
    await chat.start()

async def on_shutdown() -> None:
    await chat.stop()
```

`broadcast()`/`broadcast_json()` по-прежнему доставляют сообщение локальным
сокетам напрямую, а также публикуют его в Redis, чтобы менеджер каждого
другого воркера доставил его уже своим локальным сокетам — каждое сообщение
помечено идентификатором источника, поэтому воркер никогда не доставляет
самому себе собственную рассылку повторно. Без `redis_client` `start()`/
`stop()` — no-op, поведение не меняется (один процесс).
