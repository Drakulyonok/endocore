"""GET /v1/rooms/{room_id}/slots?day=YYYY-MM-DD — availability for one day."""

from endocore import Depends, Response, require_user_id

from Models.core import Booking
from Services.booking import get_room, validate_slot


async def handler(request, room_id, user_id=Depends(require_user_id)) -> Response:
    room = await get_room(room_id)
    day, _ = validate_slot(request.query.get("day") or "", 0)
    booked = await Booking.objects.filter(room=room, day=day).alist()
    busy = {b.hour for b in booked}
    return Response.json({
        "room_id": room.pk,
        "day": day,
        "slots": [{"hour": h, "free": h not in busy} for h in range(24)],
    })
