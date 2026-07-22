"""DELETE /v1/boards/{board_id} — owner only; cards cascade."""

from endocore import Depends, Response, require_user_id

from Services.boards import get_board, require_owner
from Services.live import broadcast


async def handler(request, board_id, user_id=Depends(require_user_id)) -> Response:
    board = await get_board(board_id)
    await require_owner(board, user_id)
    await broadcast("board.deleted", board.pk, {"board_id": board.pk})
    await board.adelete()
    return Response(None, status=204)
