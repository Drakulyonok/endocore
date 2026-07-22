"""GET /v1/boards/{board_id} — board details with all cards."""

from endocore import Depends, Response, require_user_id

from Models.core import Card
from Services.boards import board_dict, card_dict, get_board, require_member


async def handler(request, board_id, user_id=Depends(require_user_id)) -> Response:
    board = await get_board(board_id)
    await require_member(board, user_id)
    cards = await Card.objects.filter(board=board).alist()
    return Response.json({**board_dict(board), "cards": [card_dict(c) for c in cards]})
