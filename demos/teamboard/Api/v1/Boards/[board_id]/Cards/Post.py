"""POST /v1/boards/{board_id}/cards — create a card and notify the room."""

from endocore import Depends, Response, UnprocessableEntity, require_user_id

from Models.core import Card
from Services.boards import card_dict, get_board, require_member, validate_status
from Services.live import broadcast


async def handler(request, board_id, user_id=Depends(require_user_id)) -> Response:
    board = await get_board(board_id)
    await require_member(board, user_id)
    body = await request.json() or {}
    title = (body.get("title") or "").strip()
    if not title:
        raise UnprocessableEntity("title is required")

    card = await Card.objects.acreate(
        board=board,
        title=title,
        description=body.get("description") or "",
        status=validate_status(body.get("status") or "todo"),
        position=int(body.get("position") or 0),
    )
    await broadcast("card.created", board.pk, {"card": card_dict(card)})
    return Response.json(card_dict(card), status=201)
