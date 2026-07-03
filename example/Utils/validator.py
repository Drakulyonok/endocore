"""Pure util: small validators (no side effects)."""

import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value))
