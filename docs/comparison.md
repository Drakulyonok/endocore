# EndoCore vs FastAPI

Both are modern Python ASGI frameworks. They make **different bets**. This page
is an honest side-by-side so you can pick the right tool.

## The core difference

| | EndoCore | FastAPI |
|---|---|---|
| **Routing** | **File-based** — folder = path, file = method | Decorators (`@app.get(...)`) |
| **Source of truth** | The `Api/` directory tree | Python code + decorators |
| **Versioning** | First-class: `vN` folders coexist | Manual (routers/prefixes) |
| **ORM** | **Built-in**, secure, sync + async | None (bring SQLAlchemy/Tortoise) |
| **Migrations** | **Built-in** (`end migrate`, rollback, alter/rename) | Alembic (separate) |
| **CLI** | **Built-in** (`end` — create/routes/check/migrate/openapi) | None (uvicorn only) |
| **Validation** | Optional pydantic per-param | pydantic everywhere (core) |
| **DI** | `Depends` + providers by type/name | `Depends` |
| **WebSockets** | File-based `Socket.py` + pub/sub manager | Decorator `@app.websocket` |
| **Core deps** | 1 (`uvicorn`) | Starlette + pydantic + typing-extensions |
| **Docs UI** | `/docs` (Swagger) built-in | `/docs` + `/redoc` |

## When to choose EndoCore

- You want **structure to be the API** — the tree is the contract, no drift.
- You want **versioning as a first-class, guaranteed-isolated** concept.
- You want a **batteries-included** stack: ORM + migrations + cache + DI +
  WebSockets + CLI in one place, one dependency at the core.
- You like **thin endpoints + a service layer** enforced by the design.
- You want a small, **auditable** codebase you can read end-to-end.

## When to choose FastAPI

- You want the **largest ecosystem** and community, and battle-tested at scale.
- You rely on **pydantic everywhere** for request/response models and OpenAPI.
- You prefer **explicit decorator routing** and are happy wiring your own ORM.
- You need features EndoCore intentionally omits (e.g. GraphQL via Strawberry,
  a huge plugin ecosystem).

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

**EndoCore** — the route *is* the file `Api/v1/User/Post.py`:

```python
from endocore import Request, Response
from pydantic import BaseModel

class UserIn(BaseModel):
    name: str

async def handler(request: Request, data: UserIn) -> Response:
    return Response.json({"created": data.name}, status=201)
```

Same validation, same OpenAPI. The difference is **where the route lives**: in
EndoCore the URL and method are the file's location and name, so `end routes`
always shows the exact truth and versioning is a folder copy.

## Performance

Roughly on par — see [Benchmarks](benchmarks.md). On raw dispatch FastAPI is a
touch faster on trivial static routes; EndoCore is a touch faster on dynamic
routes. In production both are dominated by `uvicorn` and your DB.

## Honest limitations of EndoCore

- Smaller ecosystem and community (it's a young, focused project).
- pydantic is optional, so response models aren't validated by default.
- No GraphQL, no admin panel (by design).
- Native async DB drivers aren't used; the async ORM offloads the sync ORM to a
  threadpool (non-blocking, works for SQLite + PostgreSQL).

FastAPI is excellent. EndoCore exists for people who want the **folder-tree
idea** and a batteries-included, single-core-dependency stack.
