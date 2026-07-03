"""Pure util: hashing (no side effects)."""

import hashlib


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
