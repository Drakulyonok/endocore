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

## Origin checking

The handshake enforces same-origin by default outside `dev=True` — otherwise
a page on any other site could open a websocket to your app and ride along
on a cookie-based session (cross-site websocket hijacking), since browsers
attach cookies to a websocket handshake regardless of which site's script
opened the connection. A request with no `Origin` header (any non-browser
client) is always let through — there's no browser session to hijack there.

Rejected connections close with code `4403`. Configure it explicitly for a
real cross-origin frontend:

```python
app = Application(ws_allowed_origins=["https://app.example.com"])
```

`ws_allowed_origins="*"` disables the check entirely; leaving it unset only
relaxes it in `dev=True` (a local frontend on a different port is a
different origin).

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

### Fan-out across workers

By default rooms live in memory, so a broadcast only reaches sockets held by
*this* process — run more than one worker and each keeps its own separate
copy of every room. Pass a Redis client to share broadcasts across all of
them:

```python
from endocore.extensions import redis_client
from endocore import WebSocketManager

chat = WebSocketManager(redis_client=redis_client(url="redis://localhost:6379/0"))
```

Wire the subscriber's lifecycle into your app's startup/shutdown hooks so it
starts listening once and stops cleanly:

```python
# hooks.py
from Api.v1.Chat.Socket import chat

async def on_startup() -> None:
    await chat.start()

async def on_shutdown() -> None:
    await chat.stop()
```

`broadcast()`/`broadcast_json()` still deliver to local sockets directly, and
additionally publish to Redis so every other worker's manager delivers to
its own local sockets too — each message is tagged with an origin id so a
worker never re-delivers its own broadcast to itself. Without `redis_client`,
`start()`/`stop()` are no-ops and behavior is unchanged (single process).
