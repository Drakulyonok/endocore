"""POST /v1/boards — create a board; the creator becomes owner and member."""

from endocore import Depends, Response, UnprocessableEntity, require_user_id
from endocore.orm import aatomic

from Models.core import Board, BoardMember
from Services.boards import board_dict


async def handler(request, user_id=Depends(require_user_id)) -> Response:
    body = await request.json() or {}
    title = (body.get("title") or "").strip()
    if not title:
        raise UnprocessableEntity("title is required")

    async with aatomic():
        board = await Board.objects.acreate(owner_id=user_id, title=title)
        await BoardMember.objects.acreate(board=board, user_id=user_id)
    return Response.json(board_dict(board), status=201)
