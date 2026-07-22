"""WebSocket e2e: REST mutations reach subscribed board members live.

Everything runs in one event loop — the WS client task and the REST calls must
share it for the broadcast to land in the client's queue.
"""

from __future__ import annotations

import asyncio
import json

from Tests.conftest import acall, register


class WsClient:
    """Minimal ASGI websocket client for one connection."""

    def __init__(self, app, path: str, cookie: str | None = None) -> None:
        headers = []
        if cookie:
            headers.append((b"cookie", f"session={cookie}".encode()))
        self._scope = {"type": "websocket", "path": path,
                       "query_string": b"", "headers": headers}
        self._app = app
        self._incoming: asyncio.Queue = asyncio.Queue()
        self._outgoing: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None

    async def _receive(self):
        return await self._incoming.get()

    async def _send(self, message):
        await self._outgoing.put(message)

    async def connect(self):
        self._task = asyncio.create_task(self._app(self._scope, self._receive, self._send))
        await self._incoming.put({"type": "websocket.connect"})
        return await self.next_message()

    async def next_message(self, timeout: float = 2.0) -> dict:
        return await asyncio.wait_for(self._outgoing.get(), timeout)

    async def next_json(self, timeout: float = 2.0) -> dict:
        message = await self.next_message(timeout)
        assert message["type"] == "websocket.send", message
        return json.loads(message["text"])

    async def disconnect(self):
        await self._incoming.put({"type": "websocket.disconnect"})
        if self._task is not None:
            await asyncio.wait_for(self._task, 2.0)


def test_member_receives_live_card_events(app):
    async def scenario():
        ada = await register(app, "ada@example.com", "Ada")
        bob = await register(app, "bob@example.com", "Bob")
        _, board, _ = await acall(app, "POST", "/v1/boards",
                                  body={"title": "Live"}, cookie=ada)
        board_id = board["id"]
        await acall(app, "POST", f"/v1/boards/{board_id}/members",
                    body={"email": "bob@example.com"}, cookie=ada)

        client = WsClient(app, f"/v1/boards/{board_id}", cookie=bob)
        accept = await client.connect()
        assert accept["type"] == "websocket.accept"

        _, card, _ = await acall(app, "POST", f"/v1/boards/{board_id}/cards",
                                 body={"title": "Ship it"}, cookie=ada)
        event = await client.next_json()
        assert event["event"] == "card.created"
        assert event["card"]["title"] == "Ship it"

        await acall(app, "PATCH", f"/v1/cards/{card['id']}",
                    body={"status": "done"}, cookie=ada)
        event = await client.next_json()
        assert event["event"] == "card.updated" and event["card"]["status"] == "done"

        await acall(app, "DELETE", f"/v1/cards/{card['id']}", cookie=ada)
        event = await client.next_json()
        assert event["event"] == "card.deleted" and event["card_id"] == card["id"]

        await client.disconnect()

    asyncio.run(scenario())


def test_ws_requires_auth_and_membership(app):
    async def scenario():
        ada = await register(app, "ada@example.com", "Ada")
        mallory = await register(app, "mallory@example.com", "Mallory")
        _, board, _ = await acall(app, "POST", "/v1/boards",
                                  body={"title": "Private"}, cookie=ada)
        board_id = board["id"]

        anonymous = WsClient(app, f"/v1/boards/{board_id}")
        await anonymous.connect()
        close = await anonymous.next_message()
        assert close["type"] == "websocket.close" and close["code"] == 4401

        stranger = WsClient(app, f"/v1/boards/{board_id}", cookie=mallory)
        await stranger.connect()
        close = await stranger.next_message()
        assert close["type"] == "websocket.close" and close["code"] == 4403

    asyncio.run(scenario())
