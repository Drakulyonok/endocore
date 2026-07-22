"""Idempotency: retried purchases and retried gateway webhooks never double-charge."""

from __future__ import annotations

import asyncio
import threading

from Tests.conftest import acall, register, top_up


async def _setup(app, balance: int = 100, price: int = 30):
    cookie = await register(app, "ada@example.com", "Ada")
    await top_up(app, "ada@example.com", balance, "seed-payment")
    _, product, _ = await acall(app, "POST", "/v1/products",
                                body={"name": "VIP", "price": price}, cookie=cookie)
    return cookie, product["id"]


def test_sequential_retry_replays_the_response(app):
    async def scenario():
        cookie, product_id = await _setup(app)

        first = await acall(app, "POST", "/v1/buy", body={"product_id": product_id},
                            cookie=cookie, headers={"Idempotency-Key": "order-1"})
        retry = await acall(app, "POST", "/v1/buy", body={"product_id": product_id},
                            cookie=cookie, headers={"Idempotency-Key": "order-1"})

        assert first[0] == retry[0] == 201
        assert first[1] == retry[1]                       # byte-identical payload
        assert retry[2].get("idempotent-replay") == "true"

        _, wallet, _ = await acall(app, "GET", "/v1/wallet", cookie=cookie)
        assert wallet["balance"] == 70                    # charged exactly once
        _, history, _ = await acall(app, "GET", "/v1/purchases", cookie=cookie)
        assert len(history["purchases"]) == 1

    asyncio.run(scenario())


def test_key_is_scoped_to_its_account(app):
    async def scenario():
        cookie, product_id = await _setup(app)
        await acall(app, "POST", "/v1/buy", body={"product_id": product_id},
                    cookie=cookie, headers={"Idempotency-Key": "order-1"})

        other = await register(app, "bob@example.com", "Bob")
        status, _, _ = await acall(app, "POST", "/v1/buy",
                                   body={"product_id": product_id}, cookie=other,
                                   headers={"Idempotency-Key": "order-1"})
        assert status == 409

    asyncio.run(scenario())


def test_concurrent_same_key_charges_once(app):
    """The gateway-retry nightmare: N identical requests in flight at once."""
    cookie, product_id = asyncio.run(_setup(app))

    attempts = 6
    barrier = threading.Barrier(attempts, timeout=10)
    statuses: list[int] = []
    lock = threading.Lock()

    def attempt():
        async def go():
            barrier.wait()
            status, _, _ = await acall(app, "POST", "/v1/buy",
                                       body={"product_id": product_id},
                                       cookie=cookie,
                                       headers={"Idempotency-Key": "order-race"})
            return status

        status = asyncio.run(go())
        with lock:
            statuses.append(status)

    threads = [threading.Thread(target=attempt) for _ in range(attempts)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)

    # One request processes (201); racers replay it (201) or see 409 while it
    # is still in flight. Never a second charge.
    assert set(statuses) <= {201, 409}, statuses
    assert statuses.count(201) >= 1

    async def verify():
        _, wallet, _ = await acall(app, "GET", "/v1/wallet", cookie=cookie)
        _, history, _ = await acall(app, "GET", "/v1/purchases", cookie=cookie)
        return wallet["balance"], len(history["purchases"])

    balance, purchases = asyncio.run(verify())
    assert purchases == 1 and balance == 70


def test_webhook_retries_credit_once(app):
    async def scenario():
        cookie = await register(app, "ada@example.com", "Ada")
        results = [await top_up(app, "ada@example.com", 100, "pay-42")
                   for _ in range(3)]
        assert [r[0] for r in results] == [200, 200, 200]  # gateway sees success
        assert [r[1]["duplicate"] for r in results] == [False, True, True]
        _, wallet, _ = await acall(app, "GET", "/v1/wallet", cookie=cookie)
        assert wallet["balance"] == 100                    # credited exactly once

    asyncio.run(scenario())


def test_concurrent_webhook_retries_credit_once(app):
    cookie = asyncio.run(register(app, "ada@example.com", "Ada"))

    attempts = 6
    barrier = threading.Barrier(attempts, timeout=10)
    results: list[tuple[int, bool]] = []
    lock = threading.Lock()

    def attempt():
        async def go():
            barrier.wait()
            status, body, _ = await top_up(app, "ada@example.com", 100, "pay-42")
            return status, body["duplicate"]

        outcome = asyncio.run(go())
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=attempt) for _ in range(attempts)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)

    assert all(status == 200 for status, _ in results), results
    assert [dup for _, dup in results].count(False) == 1, results

    async def verify():
        _, wallet, _ = await acall(app, "GET", "/v1/wallet", cookie=cookie)
        return wallet["balance"]

    assert asyncio.run(verify()) == 100
