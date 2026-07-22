# Background tasks & lifecycle

Two things live on this page: code that runs when the app starts and stops
(open a DB pool, close it), and work you defer until after the response is
sent (send an email without making the client wait).

## Startup / shutdown hooks

Put lifecycle hooks in `hooks.py` at your app root. They run on the ASGI
`lifespan` events — the place to open/close pools, start schedulers, etc.

```python
# hooks.py
from Services.db import pool

async def _connect():
    await pool.open()

async def _disconnect():
    await pool.close()

on_startup = [_connect]
on_shutdown = [_disconnect]
```

Hooks can be sync or async. A failing startup hook aborts startup (reported to
the ASGI server); shutdown hooks always run.

## Background tasks (after the response)

Return work to run **after** the response is sent — great for emails, webhooks,
metrics:

```python
from endocore import Response

async def send_receipt(order_id):
    await email.send(...)

async def handler(request):
    order = create_order(...)
    return Response.json({"id": order.id}, background=lambda: send_receipt(order.id))
```

The background callable runs once the response bytes are flushed, so the
client isn't kept waiting. Whether it can block the event loop depends on
its exact shape, checked via `inspect.iscoroutinefunction`:

- Pass an `async def` function **directly** (no wrapper) and it's awaited
  straight on the event loop.
- Anything else — including the `lambda: send_receipt(order.id)` idiom
  above, which is itself a perfectly ordinary sync callable that merely
  *returns* a coroutine when called — is classified as sync and dispatched
  to a worker thread. In this specific idiom that's a harmless no-op thread
  hop (constructing the coroutine object is nearly free; the coroutine
  itself is then awaited back on the loop as normal), but it does mean a
  **genuinely blocking** sync callable passed as `background=` (a `def`
  that does real blocking I/O, not just a lambda wrapper) correctly runs off
  the loop too, exactly like a sync handler body does.

!!! note "Heavy or reliable work"
    Background tasks are best-effort and in-process. For work that must survive
    restarts or scale out, use a task queue — see the
    [Celery extension](../extensions/celery.md).

## Service integrations & the lifespan

Extensions listed in `extensions.py` are wired at boot and their
`startup`/`shutdown` are added to the lifespan automatically — so a
`RedisExtension` opens its client on startup and closes it on shutdown without
you touching `hooks.py`. See [Extensions](../extensions/index.md).
