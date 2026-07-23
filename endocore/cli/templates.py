"""File bodies emitted by ``endo create`` — thin endpoints, real (not empty).

Endpoints stay thin by construction: parse input -> call a service -> respond.
That is a hard requirement of versioning (fat endpoints copy-paste logic across
versions), so the scaffold nudges toward it from the first file.
"""

from __future__ import annotations

_ENDPOINT = '''"""{method} {url}"""

from endocore import Request, Response


async def handler(request: Request) -> Response:
    # Thin endpoint: parse input -> call a service -> return the response.
    return Response.json({{"message": "{method} {url}", "ok": True}})
'''

_SERVICE = '''"""Local (versioned) service: {name}."""


def {name}(payload: dict) -> dict:
    # Business logic lives here, not in the endpoint.
    raise NotImplementedError("implement {name}")
'''


def endpoint_body(method: str, url: str) -> str:
    """Return the source for a ``<Method>.py`` handler file."""
    return _ENDPOINT.format(method=method.upper(), url=url)


def service_body(name: str) -> str:
    """Return the source for a local service module."""
    return _SERVICE.format(name=name)
