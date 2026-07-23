"""ORM exceptions."""

from __future__ import annotations


class ORMError(Exception):
    """Base class for all ORM errors."""


class ConfigurationError(ORMError):
    """The ORM was used before a connection was configured, or misconfigured."""


class UnsafeIdentifierError(ORMError):
    """A table/column identifier failed strict validation.

    Raised before any SQL is built. Identifiers are always model-defined, but we
    validate + quote them anyway as defense in depth against injection.
    """


class FieldError(ORMError):
    """A field/lookup was used incorrectly (unknown field, bad lookup, ...)."""


class DoesNotExist(ORMError):
    """``get()`` matched no rows. Each model also gets its own subclass."""


class MultipleObjectsReturned(ORMError):
    """``get()`` matched more than one row."""


class PoolTimeoutError(ORMError):
    """Waited too long for a free pooled connection (the pool is exhausted)."""
