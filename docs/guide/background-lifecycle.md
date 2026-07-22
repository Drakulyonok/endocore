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

The background callable runs once the response bytes are flushed, so the client
isn't kept waiting.

!!! note "Heavy or reliable work"
    Background tasks are best-effort and in-process. For work that must survive
    restarts or scale out, use a task queue — see the
    [Celery extension](../extensions/celery.md).

## Service integrations & the lifespan

Extensions listed in `extensions.py` are wired at boot and their
`startup`/`shutdown` are added to the lifespan automatically — so a
`RedisExtension` opens its client on startup and closes it on shutdown without
you touching `hooks.py`. See [Extensions](../extensions/index.md).
