"""Field validators — cheap, defense-in-depth checks run on the write path.

Validation runs on ``save``/``create``/``update`` (never on filter values), so a
bad value is rejected before it is bound and sent to the database.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any

from endocore.orm.exceptions import FieldError


class ValidationError(FieldError):
    """A value failed a field's validation rules."""


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
_SLUG_RE = re.compile(r"^[-a-zA-Z0-9_]+$")


def validate_email(value: str) -> None:
    if not isinstance(value, str) or not _EMAIL_RE.match(value):
        raise ValidationError(f"invalid email address: {value!r}")


def validate_url(value: str) -> None:
    if not isinstance(value, str) or not _URL_RE.match(value):
        raise ValidationError(f"invalid URL: {value!r}")


def validate_slug(value: str) -> None:
    if not isinstance(value, str) or not _SLUG_RE.match(value):
        raise ValidationError(f"invalid slug (letters, numbers, - and _ only): {value!r}")


def validate_ip(value: str) -> None:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        raise ValidationError(f"invalid IP address: {value!r}") from None
