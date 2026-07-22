# WebSockets

A WebSocket keeps a connection open so the server can push messages to the
client at any moment — chats, live dashboards, notifications.

In EndoCore they are file-based like everything else: a file named
**`Socket.py`** (or `Ws.py`) in the Api tree is a websocket endpoint.

```python
# Api/v1/Chat/Socket.py   ->  ws /v1/chat
from endocore import WebSocket

async def handler(websocket: WebSocket) -> None:
    await websocket.accept()
    async for message in websocket.iter_text():
        await websocket.send_text(f"echo: {message}")
```

Dependency injection works here too (inject `websocket`, path params, providers,
`Depends`).

## The WebSocket object

```python
await websocket.accept(subprotocol=None)
msg  = await websocket.receive()          # raw ASGI message
text = await websocket.receive_text()
data = await websocket.receive_json()
raw  = await websocket.receive_bytes()

await websocket.send_text("hi")
await websocket.send_json({"k": "v"})
await websocket.send_bytes(b"...")
await websocket.close(code=1000)

async for text in websocket.iter_text():  # until the client disconnects
    ...
async for obj in websocket.iter_json():
    ...

websocket.path, websocket.path_params, websocket.headers, websocket.query
```

A disconnect raises `WebSocketDisconnect`; the `iter_*` helpers stop cleanly on
it. An unmatched websocket path is rejected with close code `4404`.

## Pub/Sub: rooms & broadcast

`WebSocketManager` tracks connections by room and fans messages out:

```python
from endocore import WebSocket, WebSocketManager

chat = WebSocketManager()          # one shared manager (module-level)

# Api/v1/Chat/Socket.py
async def handler(websocket: WebSocket) -> None:
    await chat.connect(websocket, room="lobby")     # accepts + joins
    try:
        async for msg in websocket.iter_text():
            await chat.broadcast(msg, room="lobby") # send to everyone in the room
    finally:
        chat.disconnect(websocket)
```

Manager API:

```python
await chat.connect(ws, room="lobby")       # accept + join
chat.add(ws, room="lobby")                 # join an already-accepted socket
chat.disconnect(ws, room="lobby")          # leave (or all rooms if room=None)
await chat.broadcast("text", room="lobby", exclude=ws)
await chat.broadcast_json({"k": "v"}, room="lobby")
await chat.send_to(ws, "text")
chat.count("lobby"); chat.members("lobby"); chat.rooms_of(ws)
```

Dead connections are dropped automatically on a failed send.

!!! note "Single process"
    The manager is in-memory (single process). For multi-worker fan-out, put a
    Redis pub/sub in front of it (publish on broadcast, subscribe per worker).
