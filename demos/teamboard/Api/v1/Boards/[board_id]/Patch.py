"""PATCH /v1/boards/{board_id} — rename (owner only)."""

from endocore import Depends, Response, UnprocessableEntity, require_user_id

from Services.boards import board_dict, get_board, require_owner
from Services.live import broadcast


async def handler(request, board_id, user_id=Depends(require_user_id)) -> Response:
    board = await get_board(board_id)
    await require_owner(board, user_id)
    body = await request.json() or {}
    title = (body.get("title") or "").strip()
    if not title:
        raise UnprocessableEntity("title is required")
    board.title = title
    await board.asave()
    await broadcast("board.renamed", board.pk, {"board": board_dict(board)})
    return Response.json(board_dict(board))
