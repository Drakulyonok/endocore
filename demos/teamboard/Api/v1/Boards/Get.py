"""GET /v1/boards — boards the current user belongs to."""

from endocore import Depends, Response, require_user_id

from Models.core import BoardMember
from Services.boards import board_dict


async def handler(request, user_id=Depends(require_user_id)) -> Response:
    memberships = await BoardMember.objects.filter(user_id=user_id).select_related("board").alist()
    return Response.json({"boards": [board_dict(m.board) for m in memberships]})
