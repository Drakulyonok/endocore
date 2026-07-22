"""The money race: concurrent purchases must never overdraft the wallet.

100 coins, price 30, 8 racers with distinct idempotency keys: exactly 3 get
201, the rest get 402, the final balance is 10 — on SQLite and, with
``ENDOCORE_TEST_POSTGRES_DSN`` set, on PostgreSQL with a real pool.
"""

from __future__ import annotations

import asyncio
import threading

from Tests.conftest import acall, register, top_up

ATTEMPTS = 8
PRICE = 30
BALANCE = 100


def test_no_overdraft_under_concurrent_purchases(app):
    async def setup():
        cookie = await register(app, "racer@example.com", "Racer")
        await top_up(app, "racer@example.com", BALANCE, "seed")
        _, product, _ = await acall(app, "POST", "/v1/products",
                                    body={"name": "VIP", "price": PRICE},
                                    cookie=cookie)
        return cookie, product["id"]

    cookie, product_id = asyncio.run(setup())

    barrier = threading.Barrier(ATTEMPTS, timeout=10)
    statuses: list[int] = []
    lock = threading.Lock()

    def attempt(n: int):
        async def go():
            barrier.wait()
            status, _, _ = await acall(app, "POST", "/v1/buy",
                                       body={"product_id": product_id},
                                       cookie=cookie,
                                       headers={"Idempotency-Key": f"order-{n}"})
            return status

        status = asyncio.run(go())
        with lock:
            statuses.append(status)

    threads = [threading.Thread(target=attempt, args=(n,)) for n in range(ATTEMPTS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)

    assert sorted(statuses) == [201] * 3 + [402] * (ATTEMPTS - 3), statuses

    async def verify():
        _, wallet, _ = await acall(app, "GET", "/v1/wallet", cookie=cookie)
        _, history, _ = await acall(app, "GET", "/v1/purchases", cookie=cookie)
        return wallet["balance"], len(history["purchases"])

    balance, purchases = asyncio.run(verify())
    assert balance == BALANCE - 3 * PRICE == 10
    assert purchases == 3
