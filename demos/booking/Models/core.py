"""Booking data model. The UNIQUE(room, day, hour) constraint is the last line
of defense against double-booking; the service checks inside a transaction
first, and this backstops any race the check cannot see."""

from endocore.orm import Model, configure, fields

from settings import DATABASE

configure(backend="sqlite", database=DATABASE)


class User(Model):
    class Meta:
        table = "bk_users"

    email = fields.CharField(max_length=120, unique=True)
    name = fields.CharField(max_length=80)
    password_hash = fields.CharField(max_length=200)
    created = fields.DateTimeField(auto_now_add=True)


class Room(Model):
    class Meta:
        table = "bk_rooms"
        ordering = ["id"]

    name = fields.CharField(max_length=80, unique=True)
    capacity = fields.IntegerField(default=4)


class Booking(Model):
    class Meta:
        table = "bk_bookings"
        ordering = ["day", "hour"]
        unique_together = ("room", "day", "hour")

    room = fields.ForeignKey(Room, on_delete="CASCADE")
    user = fields.ForeignKey(User, on_delete="CASCADE")
    day = fields.CharField(max_length=10)   # YYYY-MM-DD
    hour = fields.IntegerField()            # 0..23
    created = fields.DateTimeField(auto_now_add=True)


ALL_MODELS = (User, Room, Booking)
