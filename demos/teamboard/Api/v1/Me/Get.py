"""GET /v1/me — the current user's profile."""

from endocore import Depends, NotFound, Response, require_user_id

from Models.core import User
from Services.boards import user_dict


async def handler(request, user_id=Depends(require_user_id)) -> Response:
    user = await User.objects.filter(pk=user_id).afirst()
    if user is None:
        raise NotFound("account no longer exists")
    return Response.json(user_dict(user))
