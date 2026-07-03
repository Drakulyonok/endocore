"""ws /v1/chat — an echo websocket."""

from endocore import WebSocket


async def handler(websocket: WebSocket) -> None:
    await websocket.accept()
    async for message in websocket.iter_text():
        await websocket.send_text(f"echo: {message}")
