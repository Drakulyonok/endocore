# Booking — room-slot booking demo on EndoCore

A concurrency crash-test for the framework: bookings run inside `aatomic()`
with a `UNIQUE(room, day, hour)` backstop, and the test suite races 8 threads
for the same slot — exactly one gets **201**, the rest get **409**.

```
end dev                          # from this directory; DB auto-created on startup
python -m pytest Tests           # flow + race suite
```

## API (v1)

| Method | Path | Notes |
|--------|------|-------|
| POST | `/v1/auth/register` / `login` / `logout` | scrypt + signed-cookie sessions |
| GET/POST | `/v1/rooms` | list / add rooms |
| GET | `/v1/rooms/{id}/slots?day=YYYY-MM-DD` | 24 hourly slots with `free` flags |
| GET | `/v1/bookings` | your bookings (`select_related("room")`) |
| POST | `/v1/bookings` | `{room_id, day, hour}` → 201, or 409 if taken |
| DELETE | `/v1/bookings/{id}` | cancel your own (403 for others') |

Config via env: `BOOKING_SECRET`, `BOOKING_DB`.
