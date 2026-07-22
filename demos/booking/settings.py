"""Booking demo settings — everything overridable via environment."""

from endocore import env

SECRET = env("BOOKING_SECRET", "dev-secret-change-me")
DATABASE = env("BOOKING_DB", "booking.db")
