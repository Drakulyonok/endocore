"""POST /v1/bookings — book a slot; 409 when it is (or just became) taken."""

from endocore import Depends, Response, require_user_id

from Services.booking import book_slot, booking_dict, get_room, validate_slot


async def handler(request, user_id=Depends(require_user_id)) -> Response:
    body = await request.json() or {}
    room = await get_room(body.get("room_id"))
    day, hour = validate_slot(body.get("day") or "", body.get("hour"))
    booking = await book_slot(user_id, room, day, hour)
    return Response.json(booking_dict(booking), status=201)
