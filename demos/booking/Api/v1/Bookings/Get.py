"""GET /v1/bookings — the current user's bookings."""

from endocore import Depends, Response, require_user_id

from Models.core import Booking
from Services.booking import booking_dict


async def handler(request, user_id=Depends(require_user_id)) -> Response:
    mine = await Booking.objects.filter(user_id=user_id).select_related("room").alist()
    return Response.json({
        "bookings": [{**booking_dict(b), "room": b.room.name} for b in mine]
    })
