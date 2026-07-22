"""Happy path and error paths: wallet, catalogue, purchase, webhook."""

from __future__ import annotations

import asyncio

from Tests.conftest import acall, register, top_up


def run(coro):
    return asyncio.run(coro)


def test_topup_and_purchase_flow(app):
    async def scenario():
        cookie = await register(app, "ada@example.com", "Ada")

        status, wallet, _ = await acall(app, "GET", "/v1/wallet", cookie=cookie)
        assert status == 200 and wallet["balance"] == 0

        status, result, _ = await top_up(app, "ada@example.com", 100, "pay-001")
        assert status == 200 and result == {"ok": True, "duplicate": False}
        _, wallet, _ = await acall(app, "GET", "/v1/wallet", cookie=cookie)
        assert wallet["balance"] == 100

        status, product, _ = await acall(app, "POST", "/v1/products",
                                         body={"name": "VIP", "price": 30},
                                         cookie=cookie)
        assert status == 201

        status, bought, _ = await acall(app, "POST", "/v1/buy",
                                        body={"product_id": product["id"]},
                                        cookie=cookie,
                                        headers={"Idempotency-Key": "buy-1"})
        assert status == 201 and bought["product"] == "VIP"

        _, wallet, _ = await acall(app, "GET", "/v1/wallet", cookie=cookie)
        assert wallet["balance"] == 70
        _, history, _ = await acall(app, "GET", "/v1/purchases", cookie=cookie)
        assert len(history["purchases"]) == 1

    run(scenario())


def test_insufficient_funds(app):
    async def scenario():
        cookie = await register(app, "ada@example.com", "Ada")
        await top_up(app, "ada@example.com", 10, "pay-001")
        _, product, _ = await acall(app, "POST", "/v1/products",
                                    body={"name": "VIP", "price": 30}, cookie=cookie)
        status, body, _ = await acall(app, "POST", "/v1/buy",
                                      body={"product_id": product["id"]},
                                      cookie=cookie,
                                      headers={"Idempotency-Key": "buy-1"})
        assert status == 402 and body["error"] == "insufficient funds"
        _, wallet, _ = await acall(app, "GET", "/v1/wallet", cookie=cookie)
        assert wallet["balance"] == 10  # nothing was deducted

    run(scenario())


def test_buy_validation(app):
    async def scenario():
        cookie = await register(app, "ada@example.com", "Ada")

        status, _, _ = await acall(app, "POST", "/v1/buy", body={"product_id": 1},
                                   cookie=cookie)
        assert status == 422  # no Idempotency-Key

        status, _, _ = await acall(app, "POST", "/v1/buy", body={"product_id": 999},
                                   cookie=cookie, headers={"Idempotency-Key": "k1"})
        assert status == 404  # unknown product (result is stored and replayable)

        status, _, _ = await acall(app, "POST", "/v1/buy", body={"product_id": 1},
                                   headers={"Idempotency-Key": "k2"})
        assert status == 401  # anonymous

    run(scenario())


def test_webhook_rejects_bad_secret_and_unknown_email(app):
    async def scenario():
        await register(app, "ada@example.com", "Ada")

        status, _, _ = await acall(app, "POST", "/v1/webhook/payment",
                                   body={"payment_id": "p1",
                                         "email": "ada@example.com", "amount": 50},
                                   headers={"X-Webhook-Secret": "wrong"})
        assert status == 403

        status, _, _ = await top_up(app, "ghost@example.com", 50, "p2")
        assert status == 404

    run(scenario())
