"""ws /v1/boards/{board_id} — live updates for one board.

Auth: the WS handshake carries the same signed session cookie the HTTP
middleware issues; membership is checked before joining the room. The client
only listens — mutations go through the REST API, which broadcasts here.
"""

from endocore import WebSocket

from Services.boards import get_board, require_member, to_int
from Services.live import board_room, manager, user_id_from_cookies


async def handler(websocket: WebSocket, board_id) -> None:
    user_id = user_id_from_cookies(websocket.headers)
    if user_id is None:
        await websocket.accept()
        await websocket.close(code=4401)  # policy: unauthenticated
        return
    try:
        board = await get_board(to_int(board_id, "board id"))
        await require_member(board, user_id)
    except Exception:  # noqa: BLE001 - any access failure -> close, not 500
        await websocket.accept()
        await websocket.close(code=4403)
        return

    room = board_room(board.pk)
    await manager.connect(websocket, room)
    try:
        async for _ in websocket.iter_text():
            pass  # read-only socket: ignore client chatter, stay subscribed
    finally:
        manager.disconnect(websocket, room)
