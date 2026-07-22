"""POST /v1/rooms — add a room (any signed-in user in this demo)."""

from endocore import Conflict, Depends, Response, UnprocessableEntity, require_user_id

from Models.core import Room
from Services.booking import room_dict


async def handler(request, user_id=Depends(require_user_id)) -> Response:
    body = await request.json() or {}
    name = (body.get("name") or "").strip()
    if not name:
        raise UnprocessableEntity("name is required")
    if await Room.objects.filter(name=name).aexists():
        raise Conflict("room already exists")
    room = await Room.objects.acreate(name=name, capacity=int(body.get("capacity") or 4))
    return Response.json(room_dict(room), status=201)
