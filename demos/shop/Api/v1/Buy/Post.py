"""POST /v1/buy — idempotent purchase.

Requires an ``Idempotency-Key`` header. Retrying with the same key replays the
original response (marked ``Idempotent-Replay: true``) — the wallet is never
charged twice.
"""

from endocore import Depends, Response, UnprocessableEntity, require_user_id

from Services.shop import buy


async def handler(request, user_id=Depends(require_user_id)) -> Response:
    key = (request.headers.get("idempotency-key") or "").strip()
    if not key or len(key) > 128:
        raise UnprocessableEntity("Idempotency-Key header (1..128 chars) is required")
    body = await request.json() or {}
    return await buy(user_id, body.get("product_id"), key)
