"""POST /v1/post — create a post (via the ORM).

Thin endpoint: parse input -> use the model -> return response. User input is
bound as a query parameter by the ORM, never formatted into SQL.
"""

from endocore import HTTPError, Request, Response
from Models.blog import Post


async def handler(request: Request) -> Response:
    data = await request.json() or {}
    title = data.get("title")
    if not title:
        raise HTTPError(422, "title is required")

    post = Post.objects.create(title=title, body=data.get("body", ""))
    return Response.json({"id": post.pk, "title": post.title}, status=201)
