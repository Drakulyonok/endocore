"""Password hashing — scrypt from the stdlib (``hashlib.scrypt``, OpenSSL).

The encoded form is self-describing (``scrypt$16384$8$1$<salt>$<hash>``) so
work factors can be raised later: ``verify_password`` reads them from the
stored string, ``needs_rehash`` says when to re-hash on the next login. The
defaults (N=2**14, r=8, p=1 — 16 MiB) follow the OWASP scrypt guidance.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

__all__ = ["hash_password", "verify_password", "needs_rehash"]

_ALGORITHM = "scrypt"
_N = 2**14      # CPU/memory cost (16 MiB with r=8)
_R = 8
_P = 1
_SALT_BYTES = 16
_KEY_BYTES = 32
_MAXMEM = 64 * 1024 * 1024  # headroom above N*r*128 so OpenSSL never refuses


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, maxmem=_MAXMEM, dklen=_KEY_BYTES
    )


def hash_password(password: str) -> str:
    """Hash ``password`` with a fresh random salt. Store the returned string."""
    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")
    salt = os.urandom(_SALT_BYTES)
    key = _derive(password, salt, _N, _R, _P)
    return f"{_ALGORITHM}${_N}${_R}${_P}${_b64e(salt)}${_b64e(key)}"


def verify_password(password: str, encoded: str | None) -> bool:
    """Constant-time check of ``password`` against a stored hash.

    Returns ``False`` for a wrong password *and* for a malformed/foreign hash —
    a login path never needs to distinguish the two.

    ``encoded=None`` (unknown user) also returns ``False`` but still burns a
    full scrypt derivation, so login timing cannot enumerate accounts::

        verify_password(body["password"], user.password_hash if user else None)
    """
    if not encoded:
        try:
            _derive(password, b"\x00" * _SALT_BYTES, _N, _R, _P)
        except (TypeError, AttributeError):
            pass
        return False
    try:
        algorithm, n, r, p, salt, key = encoded.split("$")
        if algorithm != _ALGORITHM:
            return False
        expected = _b64d(key)
        candidate = _derive(password, _b64d(salt), int(n), int(r), int(p))
    except (ValueError, TypeError, AttributeError):
        return False
    return hmac.compare_digest(candidate, expected)


def needs_rehash(encoded: str) -> bool:
    """Whether a stored hash uses weaker-than-current parameters.

    Call after a successful ``verify_password`` and re-save with
    ``hash_password`` while the plaintext is at hand.
    """
    try:
        algorithm, n, r, p, _salt, _key = encoded.split("$")
    except (ValueError, AttributeError):
        return True
    return algorithm != _ALGORITHM or (int(n), int(r), int(p)) < (_N, _R, _P)
