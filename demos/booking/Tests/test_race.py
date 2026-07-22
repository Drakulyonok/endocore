"""The race: N clients grab the same slot simultaneously — exactly one wins.

Each thread runs its own event loop hitting the shared app, so requests race
through the real dispatch path: session auth -> aatomic() -> UNIQUE backstop.
"""

from __future__ import annotations

import asyncio
import threading

from Tests.conftest import acall, register

ATTEMPTS = 8


def test_exactly_one_booking_wins_the_race(app):
    async def setup():
        cookie = await register(app, "racer@example.com", "Racer")
        _, room, _ = await acall(app, "POST", "/v1/rooms", body={"name": "Thunderdome"},
                                 cookie=cookie)
        return cookie, room["id"]

    cookie, room_id = asyncio.run(setup())

    barrier = threading.Barrier(ATTEMPTS)
    statuses: list[int] = []
    lock = threading.Lock()

    def attempt():
        async def go():
            barrier.wait(timeout=10)  # maximise overlap
            status, _, _ = await acall(app, "POST", "/v1/bookings",
                                       body={"room_id": room_id,
                                             "day": "2026-08-01", "hour": 12},
                                       cookie=cookie)
            return status

        status = asyncio.run(go())
        with lock:
            statuses.append(status)

    threads = [threading.Thread(target=attempt) for _ in range(ATTEMPTS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)

    assert sorted(statuses) == [201] + [409] * (ATTEMPTS - 1), statuses

    async def verify():
        _, mine, _ = await acall(app, "GET", "/v1/bookings", cookie=cookie)
        return mine["bookings"]

    bookings = asyncio.run(verify())
    assert len(bookings) == 1


def test_different_slots_do_not_conflict(app):
    async def scenario():
        cookie = await register(app, "ada@example.com", "Ada")
        _, room, _ = await acall(app, "POST", "/v1/rooms", body={"name": "Pluto"},
                                 cookie=cookie)
        results = await asyncio.gather(*[
            acall(app, "POST", "/v1/bookings",
                  body={"room_id": room["id"], "day": "2026-08-01", "hour": hour},
                  cookie=cookie)
            for hour in range(8)
        ])
        assert [status for status, _, _ in results] == [201] * 8

    asyncio.run(scenario())
