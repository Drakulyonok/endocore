# Tutorial: a small blog API

We'll build a versioned blog API with models, thin endpoints, a service layer,
middleware, migrations and tests — the way a real EndoCore project is laid out.

By the end you'll have `v1` serving posts and comments, auth middleware, and a
`v2` that changes a contract without touching `v1`.

## 0. Set up

```bash
endo new blog && cd blog
pip install "endocore[pydantic]"
```

## 1. Models

Models live under `Models/` and configure the database on import.

```python
# Models/blog.py
from endocore.orm import Model, fields, configure, create_all

configure(backend="sqlite", database="blog.db")   # or backend="postgres", ...

class Author(Model):
    class Meta:
        ordering = ["name"]
    name  = fields.CharField(max_length=100, unique=True)
    email = fields.EmailField()

class Post(Model):
    class Meta:
        ordering = ["-id"]
    title   = fields.CharField(max_length=200)
    body    = fields.TextField(default="")
    views   = fields.IntegerField(default=0)
    author  = fields.ForeignKey(Author, related_name="posts")
    created = fields.DateTimeField(auto_now_add=True)

class Comment(Model):
    post = fields.ForeignKey(Post, related_name="comments")
    text = fields.TextField()

create_all(Author, Post, Comment)
```

!!! tip "Migrations instead of `create_all`"
    `create_all` is great for prototyping. For a real project use
    [migrations](../orm/migrations.md): `endo makemigrations && endo migrate`.

## 2. The service layer

Keep endpoints **thin** — parse input, call a service, return a response. Put
business logic in services so a new API version can reuse it.

```python
# Services/posts.py
from Models.blog import Author, Post

def create_post(*, author_name: str, title: str, body: str = "") -> Post:
    author, _ = Author.objects.get_or_create(
        name=author_name, defaults={"email": f"{author_name}@example.com"}
    )
    return Post.objects.create(author=author, title=title, body=body)

def list_posts(limit: int = 20):
    return list(Post.objects.select_related("author")[:limit])
```

## 3. Endpoints (thin)

```python
# Api/v1/Post/Get.py   (GET /v1/post)
from endocore import Request, Response
from Services.posts import list_posts

async def handler(request: Request) -> Response:
    posts = list_posts(limit=int(request.query.get("limit", "20")))
    return Response.json({"posts": [
        {"id": p.pk, "title": p.title, "author": p.author.name} for p in posts
    ]})
```

```python
# Api/v1/Post/Post.py   (POST /v1/post)
from endocore import Request, Response
from pydantic import BaseModel
from Services.posts import create_post

class PostIn(BaseModel):
    author: str
    title: str
    body: str = ""

async def handler(request: Request, data: PostIn) -> Response:   # (1)
    post = create_post(author_name=data.author, title=data.title, body=data.body)
    return Response.json({"id": post.pk, "title": post.title}, status=201)
```

1. Because `data` is annotated with a pydantic model, EndoCore validates the
   JSON body into it and returns **422** with field errors on failure. The
   schema also shows up in `/docs`.

## 4. Dynamic segments and relations

```python
# Api/v1/Post/[id]/Get.py   (GET /v1/post/42)
from endocore import Request, Response, NotFound
from Models.blog import Post

async def handler(request: Request) -> Response:
    try:
        post = Post.objects.select_related("author").get(pk=request.path_params["id"])
    except Post.DoesNotExist:
        raise NotFound("post not found")
    comments = list(post.comments.all())          # reverse FK
    return Response.json({
        "id": post.pk, "title": post.title, "author": post.author.name,
        "comments": [c.text for c in comments],
    })
```

## 5. Middleware

Register middleware in `Middleware/__init__.py`. Here we add CORS, security
headers, and a simple token auth for write methods.

```python
# Middleware/auth.py
from endocore import Request, Response, Unauthorized

async def auth_middleware(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        if request.headers.get("authorization") != "Bearer secret":
            raise Unauthorized("missing or invalid token")
    return await call_next(request)
```

```python
# Middleware/__init__.py
from endocore.middleware import cors_middleware, security_headers_middleware
from Middleware.auth import auth_middleware

middlewares = [
    cors_middleware(allow_origins=["*"]),
    security_headers_middleware(),
    auth_middleware,      # first = outermost (after framework logging)
]
```

## 6. Dependency injection

Need a DB pool, a settings object, or the current user in many handlers? Declare
it and let EndoCore build it.

```python
# providers.py
from Services.settings import get_settings
providers = {"settings": get_settings}
```

```python
# Api/v1/Config/Get.py
from endocore import Response, Depends
from Services.settings import get_settings

async def handler(request, settings = Depends(get_settings)) -> Response:
    return Response.json({"debug": settings.debug})
```

## 7. Versioning

You changed the response contract and don't want to break existing clients.
Copy the whole version:

```bash
endo version create 2        # Api/v1 -> Api/v2 (endpoints + local services)
```

Now edit `Api/v2/Post/Get.py` freely. `v1` keeps behaving **exactly** as before —
that's the guarantee. See [Versioning](../guide/versioning.md).

## 8. Migrations

```bash
endo makemigrations initial
endo migrate
# later, after model changes:
endo makemigrations add_views
endo migrate
endo showmigrations          # [x] applied  /  [ ] pending
endo rollback                # undo the last one
```

## 9. Tests

Tests live under `Tests/` and are plain `pytest`.

```python
# Tests/test_posts.py
from Services.posts import create_post
from Models.blog import Author, Comment, Post
from endocore.orm import configure, create_all

def setup_module():
    configure(backend="sqlite", database=":memory:")   # fresh DB per test run
    create_all(Author, Post, Comment)

def test_create_post():
    post = create_post(author_name="Ada", title="Hello")
    assert Post.objects.filter(title="Hello").count() == 1
```

Run them:

```bash
endo test -q
```

## 10. Serve it

```bash
endo dev                     # dev, with in-process reload
# production:
uvicorn endocore.asgi:create_app --factory --host 0.0.0.0 --port 8000
```

That's a complete, layered, versioned API. Keep going with the
[Guide](../guide/architecture.md) and the [ORM](../orm/index.md) sections.
