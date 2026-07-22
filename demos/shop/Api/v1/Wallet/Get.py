"""GET /v1/wallet — the current user's coin balance."""

from endocore import Depends, Response, require_user_id

from Services.shop import balance_of


async def handler(request, user_id=Depends(require_user_id)) -> Response:
    return Response.json({"balance": await balance_of(user_id)})
