"""Booking core: validation and the transactional book/cancel operations."""

from __future__ import annotations

import datetime

from endocore import Conflict, Forbidden, NotFound, UnprocessableEntity
from endocore.orm import aatomic

from Models.core import Booking, Room


def validate_slot(day: str, hour) -> tuple[str, int]:
    try:
        datetime.date.fromisoformat(day)
    except (TypeError, ValueError):
        raise UnprocessableEntity("day must be YYYY-MM-DD") from None
    try:
        hour = int(hour)
    except (TypeError, ValueError):
        raise UnprocessableEntity("hour must be an integer") from None
    if not 0 <= hour <= 23:
        raise UnprocessableEntity("hour must be in 0..23")
    return day, hour


async def get_room(room_id) -> Room:
    try:
        pk = int(room_id)
    except (TypeError, ValueError):
        raise NotFound("invalid room id") from None
    room = await Room.objects.filter(pk=pk).afirst()
    if room is None:
        raise NotFound("room not found")
    return room


async def book_slot(user_id: int, room: Room, day: str, hour: int) -> Booking:
    """Book atomically: check inside the transaction, UNIQUE as the backstop."""
    try:
        async with aatomic():
            taken = await Booking.objects.filter(room=room, day=day, hour=hour).aexists()
            if taken:
                raise Conflict("slot already booked")
            return await Booking.objects.acreate(
                room=room, user_id=user_id, day=day, hour=hour
            )
    except Conflict:
        raise
    except Exception as exc:  # noqa: BLE001 - a lost race hits UNIQUE(room, day, hour)
        if "unique" in str(exc).lower():
            raise Conflict("slot already booked") from None
        raise


async def cancel_booking(booking_id, user_id: int) -> None:
    try:
        pk = int(booking_id)
    except (TypeError, ValueError):
        raise NotFound("invalid booking id") from None
    booking = await Booking.objects.filter(pk=pk).afirst()
    if booking is None:
        raise NotFound("booking not found")
    if booking.user_id != user_id:
        raise Forbidden("not your booking")
    await booking.adelete()


def booking_dict(booking: Booking) -> dict:
    return {
        "id": booking.pk,
        "room_id": booking.room_id,
        "user_id": booking.user_id,
        "day": booking.day,
        "hour": booking.hour,
    }


def room_dict(room: Room) -> dict:
    return {"id": room.pk, "name": room.name, "capacity": room.capacity}
