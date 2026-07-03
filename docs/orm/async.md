# Async ORM

EndoCore runs under ASGI, where blocking the event loop hurts everyone. The ORM
provides an **async API** that runs the (battle-tested) sync ORM in a threadpool
via `asyncio.to_thread`, so your handlers stay non-blocking on both **SQLite**
and **PostgreSQL**.

!!! info "Why a threadpool instead of native async drivers"
    The threadpool offload gives non-blocking access over the exact same query
    engine, for both dialects, with zero duplicated code paths. The connection
    is guarded by a lock and (for SQLite) opened with `check_same_thread=False`,
    so cross-thread use is safe.

## Manager & QuerySet

Every common terminal operation has an `a`-prefixed async twin:

```python
# create / read
user = await User.objects.acreate(name="Ada", age=36)
user = await User.objects.aget(name="Ada")
n    = await User.objects.acount()
ok   = await User.objects.filter(active=True).aexists()
first = await User.objects.order_by("age").afirst()
last  = await User.objects.order_by("age").alast()
rows  = await User.objects.filter(age__gte=18).alist()

# async iteration
async for user in User.objects.order_by("name"):
    ...

# write
await User.objects.all().aupdate(active=True)
await User.objects.filter(spam=True).adelete()
await User.objects.abulk_create([User(name="a"), User(name="b")])
await User.objects.abulk_update(users, ["age"])

# helpers
user, created = await User.objects.aget_or_create(name="Ada", defaults={"age": 36})
stats = await User.objects.aaggregate(total=Count("*"))
```

## Instances

```python
user = await User.objects.aget(pk=1)
user.age += 1
await user.asave()
await user.arefresh_from_db()
await user.adelete()
```

## In a handler

```python
from endocore import Request, Response
from Models.blog import Post

async def handler(request: Request) -> Response:      # Api/v1/Post/Get.py
    posts = await Post.objects.order_by("-id").alist()
    return Response.json({"posts": [p.title for p in posts]})
```

## Notes

- Manager exposes async **read/create** helpers; `aupdate`/`adelete` live on the
  **QuerySet** (call `.all().aupdate(...)`), matching Django's sync semantics.
- Building a query (`filter`, `order_by`, …) is cheap and stays sync; only the
  **evaluation** is offloaded.
- Under heavy concurrency, tune the default threadpool
  (`anyio`/`asyncio` executor) or run multiple workers.
