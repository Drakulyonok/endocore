"""POST /v1/boards/{board_id}/members — invite a user by email (owner only)."""

from endocore import Conflict, Depends, NotFound, Response, require_user_id

from Models.core import BoardMember, User
from Services.boards import get_board, require_owner, user_dict


async def handler(request, board_id, user_id=Depends(require_user_id)) -> Response:
    board = await get_board(board_id)
    await require_owner(board, user_id)
    body = await request.json() or {}
    email = (body.get("email") or "").strip().lower()

    invitee = await User.objects.filter(email=email).afirst()
    if invitee is None:
        raise NotFound("no user with this email")
    if await BoardMember.objects.filter(board=board, user=invitee).aexists():
        raise Conflict("already a member")
    await BoardMember.objects.acreate(board=board, user=invitee)
    return Response.json({"invited": user_dict(invitee)}, status=201)
