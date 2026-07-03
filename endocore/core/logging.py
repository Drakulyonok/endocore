"""Logging: a thin wrapper over stdlib ``logging`` + sensitive-data masking.

We do not write a logger from scratch (levels, formatters, handlers already
exist). We configure one named logger and provide :func:`mask`, which must run
on payloads **before** they are written — the request-logging middleware sees the
raw inbound JSON, so masking has to live at the logger layer, not the DB layer
(TZ §7).
"""

from __future__ import annotations

import logging
from typing import Any

#: Keys whose values are replaced with ``MASK`` before logging.
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "secret",
        "api_key",
        "apikey",
        "credit_card",
    }
)

MASK = "***"

#: ``[INFO]  POST /v2/user/role 12ms`` — the level in brackets, then the message.
_LOG_FORMAT = "[%(levelname)s] %(message)s"

_CONFIGURED = False


def get_logger(name: str = "endocore") -> logging.Logger:
    """Return the framework logger, configuring the root handler once."""
    global _CONFIGURED
    logger = logging.getLogger(name)
    if not _CONFIGURED:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        _CONFIGURED = True
    return logger


def mask(data: Any, keys: frozenset[str] = SENSITIVE_KEYS) -> Any:
    """Return a copy of ``data`` with sensitive values replaced by ``MASK``.

    Recurses through dicts and lists; other values pass through unchanged.
    Key matching is case-insensitive.
    """
    if isinstance(data, dict):
        return {
            key: (MASK if isinstance(key, str) and key.lower() in keys else mask(value, keys))
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [mask(item, keys) for item in data]
    return data
