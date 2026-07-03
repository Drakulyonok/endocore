# Logging

Logging is built into the core as a wrapper over the standard library `logging`,
plus an always-on middleware that times requests and **masks sensitive data**.

## What gets logged

Each request produces a line like:

```text
[INFO]  POST /v1/user/role 201 3ms id=8f2c… payload={'name': 'Ada', 'password': '***'}
[ERROR] GET /v1/user/0 -> 500 5ms id=… payload=… <traceback>
```

- method, path, status, duration, and a **request id**;
- the request payload with **sensitive keys masked** (`password`, `token`,
  `authorization`, `secret`, `api_key`, …) *before* anything is written;
- on error, the full traceback.

## Why masking is at the logger layer

The logging middleware sees the raw inbound JSON — before any encryption or
storage. Masking there is the only place that reliably keeps secrets out of the
logs. Encryption-at-rest in the DB doesn't help the log stream.

## Request IDs

Every request gets an `X-Request-ID` (an inbound one is honoured), echoed on the
response and included in every log line — so you can trace one request end to
end. Behind a proxy, forward the header.

## Colored dev output

When stderr is a TTY, the level prefix is colored for readability. When output
is redirected (files, aggregators), plain text is used automatically.

## Using the logger yourself

```python
from endocore import get_logger
log = get_logger()          # the configured "endocore" logger

log.info("processed order %s", order_id)
```

Mask a structure manually:

```python
from endocore.core.logging import mask
mask({"password": "x", "name": "Ada"})     # {"password": "***", "name": "Ada"}
```

## Adjusting levels / handlers

`get_logger()` returns a standard `logging.Logger`, so configure it as usual:

```python
import logging
logging.getLogger("endocore").setLevel(logging.WARNING)
```
