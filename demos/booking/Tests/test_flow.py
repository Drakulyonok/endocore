"""Booking flow: rooms, availability, booking, conflicts, cancellation."""

from __future__ import annotations

import asyncio

from Tests.conftest import acall, register


def run(coro):
    return asyncio.run(coro)


def test_full_booking_flow(app):
    async def scenario():
        cookie = await register(app, "ada@example.com", "Ada")

        status, room, _ = await acall(app, "POST", "/v1/rooms",
                                      body={"name": "Mercury", "capacity": 6},
                                      cookie=cookie)
        assert status == 201
        room_id = room["id"]

        status, slots, _ = await acall(app, "GET", f"/v1/rooms/{room_id}/slots",
                                       query="day=2026-08-01", cookie=cookie)
        assert status == 200
        assert all(s["free"] for s in slots["slots"])

        status, booking, _ = await acall(app, "POST", "/v1/bookings",
                                         body={"room_id": room_id,
                                               "day": "2026-08-01", "hour": 10},
                                         cookie=cookie)
        assert status == 201

        status, slots, _ = await acall(app, "GET", f"/v1/rooms/{room_id}/slots",
                                       query="day=2026-08-01", cookie=cookie)
        taken = [s for s in slots["slots"] if not s["free"]]
        assert [s["hour"] for s in taken] == [10]

        status, _, _ = await acall(app, "POST", "/v1/bookings",
                                   body={"room_id": room_id,
                                         "day": "2026-08-01", "hour": 10},
                                   cookie=cookie)
        assert status == 409

        status, mine, _ = await acall(app, "GET", "/v1/bookings", cookie=cookie)
        assert len(mine["bookings"]) == 1 and mine["bookings"][0]["room"] == "Mercury"

        status, _, _ = await acall(app, "DELETE", f"/v1/bookings/{booking['id']}",
                                   cookie=cookie)
        assert status == 204
        status, mine, _ = await acall(app, "GET", "/v1/bookings", cookie=cookie)
        assert mine["bookings"] == []

    run(scenario())


def test_cannot_cancel_someone_elses_booking(app):
    async def scenario():
        ada = await register(app, "ada@example.com", "Ada")
        bob = await register(app, "bob@example.com", "Bob")
        _, room, _ = await acall(app, "POST", "/v1/rooms", body={"name": "Venus"},
                                 cookie=ada)
        _, booking, _ = await acall(app, "POST", "/v1/bookings",
                                    body={"room_id": room["id"],
                                          "day": "2026-08-01", "hour": 9},
                                    cookie=ada)
        status, _, _ = await acall(app, "DELETE", f"/v1/bookings/{booking['id']}",
                                   cookie=bob)
        assert status == 403

    run(scenario())


def test_validation(app):
    async def scenario():
        cookie = await register(app, "ada@example.com", "Ada")
        _, room, _ = await acall(app, "POST", "/v1/rooms", body={"name": "Mars"},
                                 cookie=cookie)
        for payload in [
            {"room_id": room["id"], "day": "not-a-date", "hour": 10},
            {"room_id": room["id"], "day": "2026-08-01", "hour": 24},
            {"room_id": room["id"], "day": "2026-08-01", "hour": "x"},
        ]:
            status, _, _ = await acall(app, "POST", "/v1/bookings", body=payload,
                                       cookie=cookie)
            assert status == 422, payload
        status, _, _ = await acall(app, "POST", "/v1/bookings",
                                   body={"room_id": 999, "day": "2026-08-01",
                                         "hour": 1}, cookie=cookie)
        assert status == 404

    run(scenario())
