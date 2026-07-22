"""Shop core: idempotent purchases and webhook credits.

Purchase protocol (client sends an ``Idempotency-Key`` header):
1. **Claim** the key — INSERT into ``shop_idempotency`` (UNIQUE). Losing the
   race / retrying means the key exists: replay the stored response, or 409
   if the original request is still processing.
2. **Process** — conditional spend + purchase row in one transaction.
3. **Store** the response on the record; retries from now on replay it.

Webhook credits are simpler: the payment INSERT (UNIQUE external_id) and the
wallet credit share one transaction, so a retried webhook is a clean no-op.
"""

from __future__ import annotations

import json

from endocore import Conflict, NotFound, Response
from endocore.orm import F, aatomic

from Models.core import IdempotencyRecord, Payment, Product, Purchase, User, Wallet


def _is_unique_violation(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "unique" in text or "duplicate" in text


# -- wallet primitives -------------------------------------------------------

async def spend(user_id: int, amount: int) -> bool:
    """Atomically deduct ``amount`` if the balance allows it.

    A conditional UPDATE is the only spend that survives READ COMMITTED
    concurrency — check-then-write would overdraft under parallel requests.
    """
    won = await Wallet.objects.filter(
        user_id=user_id, balance__gte=amount
    ).aupdate(balance=F("balance") - amount)
    return bool(won)


async def credit(user_id: int, amount: int) -> None:
    await Wallet.objects.filter(user_id=user_id).aupdate(balance=F("balance") + amount)


async def balance_of(user_id: int) -> int:
    wallet = await Wallet.objects.filter(user_id=user_id).afirst()
    if wallet is None:
        raise NotFound("wallet not found")
    return wallet.balance


# -- idempotent purchase -----------------------------------------------------

async def claim_key(key: str, user_id: int) -> IdempotencyRecord | Response:
    """Claim ``key`` for this request. Returns the fresh record, or a replayed
    Response when the key was already used (409 while still processing)."""
    try:
        async with aatomic():
            return await IdempotencyRecord.objects.acreate(key=key, user_id=user_id)
    except Exception as exc:  # noqa: BLE001
        if not _is_unique_violation(exc):
            raise
    record = await IdempotencyRecord.objects.aget(key=key)
    if record.user_id != user_id:
        raise Conflict("idempotency key belongs to another account")
    if record.status_code == 0:
        raise Conflict("request with this idempotency key is still processing; retry later")
    response = Response.json(json.loads(record.body), status=record.status_code)
    response.headers["Idempotent-Replay"] = "true"
    return response


async def finish_key(record: IdempotencyRecord, status_code: int, payload: dict) -> Response:
    record.status_code = status_code
    record.body = json.dumps(payload)
    await record.asave()
    return Response.json(payload, status=status_code)


async def buy(user_id: int, product_id, idempotency_key: str) -> Response:
    claimed = await claim_key(idempotency_key, user_id)
    if isinstance(claimed, Response):
        return claimed

    product = await Product.objects.filter(pk=_to_int(product_id)).afirst()
    if product is None:
        return await finish_key(claimed, 404, {"error": "product not found"})

    async with aatomic():
        if not await spend(user_id, product.price):
            payload: dict = {"error": "insufficient funds"}
            status = 402
        else:
            purchase = await Purchase.objects.acreate(
                user_id=user_id, product=product, price=product.price
            )
            payload = {"purchase_id": purchase.pk, "product": product.name,
                       "price": product.price}
            status = 201
    return await finish_key(claimed, status, payload)


# -- gateway webhook ---------------------------------------------------------

async def apply_gateway_payment(external_id: str, email: str, amount: int) -> dict:
    """Credit a gateway payment exactly once, no matter how often it retries."""
    if not external_id or amount <= 0:
        raise NotFound("invalid payment payload")
    user = await User.objects.filter(email=email.strip().lower()).afirst()
    if user is None:
        raise NotFound("no account for this email")
    try:
        async with aatomic():
            await Payment.objects.acreate(external_id=external_id, user=user, amount=amount)
            await credit(user.pk, amount)
    except Exception as exc:  # noqa: BLE001
        if _is_unique_violation(exc):
            return {"ok": True, "duplicate": True}  # retried webhook: already applied
        raise
    return {"ok": True, "duplicate": False}


def _to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise NotFound("invalid id") from None
