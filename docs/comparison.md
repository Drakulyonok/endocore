# EndoCore vs FastAPI

Both are modern Python ASGI frameworks — they just place different bets.

## The short version

| | EndoCore | FastAPI |
|---|---|---|
| Routing | File-based: folder = path, file = method | Decorators (`@app.get(...)`) |
| Source of truth | The `Api/` directory tree | Python code + decorators |
| Versioning | Built in: `vN` folders coexist | Manual (routers/prefixes) |
| ORM | Built in, sync + async | None (bring SQLAlchemy/Tortoise) |
| Migrations | Built in (`endo migrate`, rollback) | Alembic (separate) |
| CLI | Built in (`endo`) | None (uvicorn only) |
| Validation | pydantic, optional per-param | pydantic everywhere (core) |
| DI | `Depends` + providers by type/name | `Depends` |
| WebSockets | File-based `Socket.py` + pub/sub | `@app.websocket` |
| Core dependencies | 1 (`uvicorn`) | Starlette + pydantic + typing-extensions |
| Docs UI | `/docs` (Swagger) | `/docs` + `/redoc` |

## Pick EndoCore if

- you want the folder tree to be the API contract, with no way for code and
  routes to drift;
- you need versioning where a new version can't break the old one;
- you'd rather get the ORM, migrations, cache, DI, WebSockets and a CLI from
  one package;
- you want a codebase small enough to actually read.

## Pick FastAPI if

- you want the biggest ecosystem and community;
- pydantic models everywhere is how you like to work;
- you prefer decorator routing and choosing your own ORM.

## Same task, both ways

**FastAPI**

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class UserIn(BaseModel):
    name: str

@app.post("/v1/user")
async def create_user(data: UserIn):
    return {"created": data.name}
```

**EndoCore** — the route is the file `Api/v1/User/Post.py`:

```python
from endocore import Request, Response
from pydantic import BaseModel

class UserIn(BaseModel):
    name: str

async def handler(request: Request, data: UserIn) -> Response:
    return Response.json({"created": data.name}, status=201)
```

Same validation, same OpenAPI. The difference is where the route lives: in
EndoCore the URL and method are the file's location and name, `endo routes`
prints the tree, and a new API version is a folder copy.

## Performance

On pure in-process dispatch EndoCore is faster — about 2.2× on a static route
and 3.6× on a dynamic one — simply because it does less per request. Method and
caveats are in [Benchmarks](benchmarks.md). In a real app the database
dominates either way.

## Good to know

- Body validation needs the `pydantic` extra. With it installed, a handler
  parameter annotated with a `BaseModel` is validated from the JSON body:
  422 on failure, schema in `/docs`. See
  [Dependency Injection](guide/dependency-injection.md).
- The async ORM is the sync engine on a threadpool. Use the `a*` methods
  (`aget`, `alist`, `asave`, …) and the event loop stays free. See the
  [Async ORM](orm/async.md).

FastAPI is excellent. EndoCore is for people who want the folder-tree idea
with batteries included.
