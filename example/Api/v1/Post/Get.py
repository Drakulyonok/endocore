"""GET /v1/post — list posts (via the ORM)."""

from endocore import Request, Response
from Models.blog import Post


async def handler(request: Request) -> Response:
    posts = list(Post.objects.order_by("-id").values("id", "title", "views"))
    return Response.json({"posts": posts})
