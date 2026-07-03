"""GLOBAL service — shared across all versions."""


def can(user: dict, action: str) -> bool:
    # Demo stub.
    return bool(user) and action in {"read", "write"}
