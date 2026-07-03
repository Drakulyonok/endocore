"""Framework-level exceptions."""

from __future__ import annotations


class EndoCoreError(Exception):
    """Base class for all framework errors."""


class HandlerContractError(EndoCoreError):
    """A handler file does not satisfy the endpoint contract.

    e.g. it is missing the required ``handler`` callable.
    """


class BootError(EndoCoreError):
    """A handler file failed to import during boot.

    Collected (not raised) so one broken file never brings down the whole boot.
    """

    def __init__(self, path, error: BaseException, tb: str) -> None:
        self.path = path
        self.error = error
        self.tb = tb
        super().__init__(f"{path}: {error!r}")


class HTTPError(EndoCoreError):
    """Raised inside a handler to short-circuit with a status code."""

    def __init__(self, status: int, detail: str | None = None) -> None:
        self.status = status
        self.detail = detail or ""
        super().__init__(f"HTTP {status}: {self.detail}")
