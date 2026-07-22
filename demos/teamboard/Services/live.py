"""Live board updates: one WebSocketManager, one room per board.

REST handlers broadcast events after each mutation; the socket endpoint joins
the board's room. Session auth for the WS handshake reuses the framework's
Signer — the same signed cookie the HTTP middleware issues.
"""

from http.cookies import SimpleCookie

from endocore import WebSocketManager
from endocore.core.auth import SESSION_KEY
from endocore.core.signing import BadSignature, Signer

from settings import SECRET

manager = WebSocketManager()


def board_room(board_id) -> str:
    return f"board:{board_id}"


async def broadcast(event: str, board_id, payload: dict) -> None:
    await manager.broadcast_json({"event": event, **payload}, room=board_room(board_id))


def user_id_from_cookies(headers: dict[str, str]):
    """Extract the logged-in user's id from a WS handshake's session cookie."""
    jar = SimpleCookie()
    try:
        jar.load(headers.get("cookie", ""))
    except Exception:  # noqa: BLE001
        return None
    if "session" not in jar:
        return None
    try:
        session = Signer(SECRET, salt="endocore.session").loads(jar["session"].value)
    except (BadSignature, ValueError):
        return None
    return session.get(SESSION_KEY) if isinstance(session, dict) else None
