"""GET /v1/user/{id} — fetch a single user by dynamic path segment."""

from endocore import HTTPError, Request, Response


async def handler(request: Request) -> Response:
    user_id = request.path_params["id"]
    if user_id == "0":
        # Handlers can raise to short-circuit with a status code.
        raise HTTPError(404, "user not found")
    return Response.json({"id": user_id, "name": f"user-{user_id}"})
