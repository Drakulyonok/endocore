"""POST /v1/webhook/payment — the payment gateway's callback.

Gateways retry until they see a 2xx, so this endpoint must be idempotent:
``external_id`` is UNIQUE and the credit shares its transaction, making every
retry a no-op that still answers 200.
"""

import hmac

from endocore import Forbidden, Response, UnprocessableEntity

from Services.shop import apply_gateway_payment
from settings import WEBHOOK_SECRET


async def handler(request) -> Response:
    provided = request.headers.get("x-webhook-secret") or ""
    if not hmac.compare_digest(provided, WEBHOOK_SECRET):
        raise Forbidden("bad webhook signature")

    body = await request.json() or {}
    external_id = (body.get("payment_id") or "").strip()
    email = body.get("email") or ""
    try:
        amount = int(body.get("amount"))
    except (TypeError, ValueError):
        raise UnprocessableEntity("amount must be an integer") from None
    if not external_id or amount <= 0:
        raise UnprocessableEntity("payment_id and a positive amount are required")

    return Response.json(await apply_gateway_payment(external_id, email, amount))
