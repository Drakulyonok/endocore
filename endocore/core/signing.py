"""Signed values (for tamper-proof cookies) — HMAC-SHA256 from the stdlib.

A signed value is ``payload.timestamp.signature`` (all url-safe base64). The
signature is verified in constant time; an optional ``max_age`` rejects stale
values. Use it for session ids / CSRF tokens carried in cookies.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


class BadSignature(Exception):
    """A signed value was missing, malformed, tampered with, or expired."""


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


class Signer:
    """Signs and verifies strings with a secret key."""

    def __init__(self, secret: str | bytes, *, salt: str = "endocore.signer") -> None:
        secret_bytes = secret.encode("utf-8") if isinstance(secret, str) else secret
        self.key = hashlib.sha256(salt.encode("utf-8") + b":" + secret_bytes).digest()

    def _signature(self, value: bytes) -> str:
        return _b64e(hmac.new(self.key, value, hashlib.sha256).digest())

    def sign(self, value: str) -> str:
        ts = _b64e(int(time.time()).to_bytes(8, "big"))
        payload = f"{value}.{ts}"
        return f"{payload}.{self._signature(payload.encode('utf-8'))}"

    def unsign(self, signed: str, *, max_age: int | None = None) -> str:
        try:
            value, ts, signature = signed.rsplit(".", 2)
        except ValueError:
            raise BadSignature("malformed signed value") from None
        payload = f"{value}.{ts}"
        expected = self._signature(payload.encode("utf-8"))
        if not hmac.compare_digest(expected, signature):
            raise BadSignature("signature mismatch")
        if max_age is not None:
            age = time.time() - int.from_bytes(_b64d(ts), "big")
            if age > max_age:
                raise BadSignature(f"signature expired ({int(age)}s > {max_age}s)")
        return value

    # Convenience for structured data.
    def dumps(self, obj: Any) -> str:
        return self.sign(_b64e(json.dumps(obj, separators=(",", ":")).encode("utf-8")))

    def loads(self, signed: str, *, max_age: int | None = None) -> Any:
        return json.loads(_b64d(self.unsign(signed, max_age=max_age)))
