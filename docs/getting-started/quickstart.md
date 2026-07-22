# Quickstart

Build a running API in about a minute. No config files and no route
registration — you create folders and files, EndoCore serves them.

## 1. Scaffold a project

```bash
end new blog
cd blog
```

!!! note "PowerShell"
    In PowerShell type `endo` instead of `end` (`endo new blog`) — `end` is a
    reserved word there. Same CLI, different name.

You get a ready structure:

```text
blog/
  Api/
    v1/
      Health/
        Get.py          # GET /v1/health
  Middleware/
    __init__.py         # register middleware here
  Services/  Models/  Utils/  Tests/
  hooks.py              # startup / shutdown hooks
  extensions.py         # service integrations (Redis, cache, ...)
```

## 2. Run the dev server

```bash
end dev
```

You should see something like:

```text
[INFO] EndoCore booted: loaded 1 route, 0 middleware, 0 files with errors
[INFO] Uvicorn running on http://127.0.0.1:8000
```

Visit `http://127.0.0.1:8000/v1/health` — you'll get `{"status": "ok"}`.
Open `http://127.0.0.1:8000/docs` for the interactive **Swagger UI**, where you
can try every endpoint from the browser.

## 3. Add an endpoint

Either scaffold it:

```bash
end create user/profile get
# -> Api/v1/User/Profile/Get.py   (GET /v1/user/profile)
```

…or just create the file. **The folder is the path, the file name is the method.**

```python
# Api/v1/User/Profile/Get.py
from endocore import Request, Response

async def handler(request: Request) -> Response:
    return Response.json({"name": "Ada", "role": "admin"})
```

Save the file — the dev server picks it up without a restart. Open
`http://127.0.0.1:8000/v1/user/profile` and the endpoint is live.

## 4. Dynamic segments

A folder named `[id]` captures a path parameter:

```python
# Api/v1/User/[id]/Get.py
from endocore import Request, Response

async def handler(request: Request) -> Response:
    user_id = request.path_params["id"]         # "42" for /v1/user/42
    return Response.json({"id": user_id})
```

## 5. Read input

```python
# Api/v1/User/Post.py   (POST /v1/user)
from endocore import Request, Response, HTTPError

async def handler(request: Request) -> Response:
    data = await request.json()
    if not data.get("name"):
        raise HTTPError(422, "name is required")
    return Response.json({"created": data["name"]}, status=201)
```

`request` also gives you `request.query` (query params), `request.headers`,
`request.cookies`, and `await request.form()` / `await request.files()`.

## 6. Add the ORM

```python
# Models/blog.py
from endocore.orm import Model, fields, configure, create_all

configure(backend="sqlite", database="blog.db")

class Post(Model):
    title = fields.CharField(max_length=200)
    body  = fields.TextField(default="")

create_all(Post)
```

```python
# Api/v1/Post/Post.py   (POST /v1/post)
from endocore import Request, Response
from Models.blog import Post

async def handler(request: Request) -> Response:
    data = await request.json()
    post = Post.objects.create(title=data["title"], body=data.get("body", ""))
    return Response.json({"id": post.pk, "title": post.title}, status=201)
```

## 7. Inspect your app

```bash
end routes         # list every route + the file it maps to
end check          # find broken handlers, duplicate routes
end openapi        # print the OpenAPI schema
```

That's the whole loop. Next, follow the [Tutorial](tutorial.md) to build a
complete, versioned API with services, middleware and migrations.
