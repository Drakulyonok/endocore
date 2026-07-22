"""DELETE /v1/bookings/{booking_id} — cancel your own booking."""

from endocore import Depends, Response, require_user_id

from Services.booking import cancel_booking


async def handler(request, booking_id, user_id=Depends(require_user_id)) -> Response:
    await cancel_booking(booking_id, user_id)
    return Response(None, status=204)
