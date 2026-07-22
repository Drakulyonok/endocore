"""DELETE /v1/cards/{card_id} — remove a card and notify the room."""

from endocore import Depends, Response, require_user_id

from Services.boards import get_card_for
from Services.live import broadcast


async def handler(request, card_id, user_id=Depends(require_user_id)) -> Response:
    card = await get_card_for(card_id, user_id)
    board_id, card_pk = card.board_id, card.pk
    await card.adelete()
    await broadcast("card.deleted", board_id, {"card_id": card_pk})
    return Response(None, status=204)
