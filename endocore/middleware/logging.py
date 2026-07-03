"""Request-logging middleware: timing + masked payload + error traceback.

Logs each request as ``[INFO] POST /v2/user/role 12ms`` and, on an unhandled
exception, logs the masked payload and traceback and returns a 500 — one bad
handler must not kill the connection silently.
"""

from __future__ import annotations

import time
import traceback
from typing import Any

from endocore.core.logging import get_logger, mask
from endocore.core.middleware import Next
from endocore.core.request import Request
from endocore.core.response import Response

_logger = get_logger()


async def _safe_payload(request: Request) -> Any:
    """Best-effort masked JSON payload for the log line (never raises)."""
    try:
        body = await request.json()
    except Exception:
        return None
    return mask(body) if body is not None else None


async def logging_middleware(request: Request, call_next: Next) -> Response:
    """Measure duration, mask the payload, log the outcome, convert errors -> 500."""
    start = time.perf_counter()
    # Read the payload up front (before the handler) so it is captured even when
    # the handler raises. Masking happens here, at the logger layer, before the
    # raw JSON is ever written anywhere (TZ §7).
    payload = await _safe_payload(request)

    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000
        _logger.error(
            "%s %s -> 500 %.0fms payload=%s\n%s",
            request.method,
            request.path,
            elapsed_ms,
            payload,
            traceback.format_exc().rstrip(),
        )
        return Response.json({"error": "Internal Server Error"}, status=500)

    elapsed_ms = (time.perf_counter() - start) * 1000
    suffix = f" payload={payload}" if payload is not None else ""
    _logger.info(
        "%s %s %d %.0fms%s",
        request.method,
        request.path,
        response.status,
        elapsed_ms,
        suffix,
    )
    return response
