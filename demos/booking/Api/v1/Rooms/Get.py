"""GET /v1/rooms — all rooms."""

from endocore import Depends, Response, require_user_id

from Models.core import Room
from Services.booking import room_dict


async def handler(request, user_id=Depends(require_user_id)) -> Response:
    rooms = await Room.objects.all().alist()
    return Response.json({"rooms": [room_dict(r) for r in rooms]})
