"""POST /v1/user/role — create a role for a user.

Thin endpoint: parse input -> call service -> return response.
"""

from endocore import Request, Response

# Local (versioned) service — lives under Api/v1/User/Services/.
from Api.v1.User.Services.create_role import create_role


async def handler(request: Request) -> Response:
    payload = await request.json()
    role = create_role(payload)
    return Response.json(role, status=201)
