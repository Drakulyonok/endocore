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

!!! note "Один процесс"
    Менеджер живёт в памяти (один процесс). Для рассылки между несколькими
    воркерами поставьте перед ним Redis pub/sub (publish при broadcast,
    subscribe в каждом воркере).
