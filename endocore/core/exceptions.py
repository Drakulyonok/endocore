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
    """Raised inside a handler to short-circuit with a status code.

    Subclasses set a default status and message, so handlers can write
    ``raise NotFound()`` or ``raise Forbidden("nope")``.
    """

    status = 500
    message = "Internal Server Error"

    def __init__(self, status: int | None = None, detail: str | None = None) -> None:
        if status is not None:
            self.status = status
        self.detail = detail if detail is not None else self.message
        super().__init__(f"HTTP {self.status}: {self.detail}")


class BadRequest(HTTPError):
    status, message = 400, "Bad Request"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(None, detail)


class Unauthorized(HTTPError):
    status, message = 401, "Unauthorized"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(None, detail)


class Forbidden(HTTPError):
    status, message = 403, "Forbidden"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(None, detail)


class NotFound(HTTPError):
    status, message = 404, "Not Found"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(None, detail)


class MethodNotAllowed(HTTPError):
    status, message = 405, "Method Not Allowed"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(None, detail)


class Conflict(HTTPError):
    status, message = 409, "Conflict"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(None, detail)


class PayloadTooLarge(HTTPError):
    status, message = 413, "Payload Too Large"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(None, detail)


class UnprocessableEntity(HTTPError):
    status, message = 422, "Unprocessable Entity"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(None, detail)


class TooManyRequests(HTTPError):
    status, message = 429, "Too Many Requests"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(None, detail)


#: Django-style alias.
PermissionDenied = Forbidden
