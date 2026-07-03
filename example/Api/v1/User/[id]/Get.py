"""GET /v1/user/{id} — fetch a single user by dynamic path segment."""

from endocore import Request, Response


async def handler(request: Request) -> Response:
    user_id = request.path_params["id"]
    return Response.json({"id": user_id, "name": f"user-{user_id}"})
