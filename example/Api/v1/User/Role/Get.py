"""GET /v1/user/role — list roles."""

from endocore import Request, Response


async def handler(request: Request) -> Response:
    # Demo data; a real handler would call a service.
    return Response.json({"roles": ["admin", "editor", "viewer"]})
