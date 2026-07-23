"""Logging: a thin wrapper over stdlib ``logging`` + sensitive-data masking.

We do not write a logger from scratch (levels, formatters, handlers already
exist). We configure one named logger and provide :func:`mask`, which must run
on payloads **before** they are written — the request-logging middleware sees the
raw inbound JSON, so masking has to live at the logger layer, not the DB layer
(TZ §7).
"""

from __future__ import annotations

import logging
import sys
from typing import Any

#: Substrings (not exact keys) whose presence in a field name masks its value —
#: catches ``old_password``/``new_password``/``X-Api-Key``/``user_token`` too,
#: not just a field literally named ``password``.
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "token",
        "authorization",
        "secret",
        "api_key",
        "credit_card",
    }
)

MASK = "***"

#: ``[INFO]  POST /v2/user/role 12ms`` — the level in brackets, then the message.
_LOG_FORMAT = "[%(levelname)s] %(message)s"

_LEVEL_COLORS = {
    "DEBUG": "\033[36m",     # cyan
    "INFO": "\033[32m",      # green
    "WARNING": "\033[33m",   # yellow
    "ERROR": "\033[31m",     # red
    "CRITICAL": "\033[1;31m",
}
_RESET = "\033[0m"


class _ColorFormatter(logging.Formatter):
    """Colors the ``[LEVEL]`` prefix for readable dev logs on a TTY."""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        color = _LEVEL_COLORS.get(record.levelname)
        if color and message.startswith(f"[{record.levelname}]"):
            prefix = f"[{record.levelname}]"
            return f"{color}{prefix}{_RESET}" + message[len(prefix):]
        return message


_CONFIGURED = False


def get_logger(name: str = "endocore") -> logging.Logger:
    """Return the framework logger, configuring the root handler once.

    Uses colored output when stderr is a terminal (nicer dev DX), plain
    otherwise (so redirected logs stay clean).
    """
    global _CONFIGURED
    logger = logging.getLogger(name)
    if not _CONFIGURED:
        handler = logging.StreamHandler()
        use_color = getattr(handler.stream, "isatty", lambda: False)()
        formatter = _ColorFormatter(_LOG_FORMAT) if use_color else logging.Formatter(_LOG_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        _CONFIGURED = True
    return logger


def _looks_sensitive(key: Any, hints: frozenset[str]) -> bool:
    if not isinstance(key, str):
        return False
    normalized = key.lower().replace("-", "").replace("_", "")
    return any(hint in normalized for hint in hints)


def mask(data: Any, keys: frozenset[str] = SENSITIVE_KEYS) -> Any:
    """Return a copy of ``data`` with sensitive values replaced by ``MASK``.

    Recurses through dicts and lists; other values pass through unchanged.
    A key matches if any hint is a substring of it (case/separator-insensitive:
    ``old_password``, ``X-Api-Key`` and ``apikey`` all match), not just an exact
    field name.
    """
    hints = frozenset(hint.replace("_", "") for hint in keys)
    if isinstance(data, dict):
        return {
            key: (MASK if _looks_sensitive(key, hints) else mask(value, keys))
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [mask(item, keys) for item in data]
    return data
