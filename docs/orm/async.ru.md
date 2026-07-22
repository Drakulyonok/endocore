# Асинхронная ORM

EndoCore работает под ASGI, где блокировка event loop вредит всем. ORM
предоставляет **async API**, который запускает (проверенную боем) синхронную
ORM в тредпуле через `asyncio.to_thread`, так что обработчики остаются
неблокирующими и на **SQLite**, и на **PostgreSQL**.

!!! info "Почему тредпул, а не нативные async-драйверы"
    Выгрузка в тредпул даёт неблокирующий доступ поверх ровно того же движка
    запросов, для обоих диалектов, без дублирования кода. У каждого алиаса —
    небольшой пул соединений (`configure(..., pool_size=N)`; SQLite 1,
    PostgreSQL 5), а SQLite-соединения открываются с `check_same_thread=False`,
    так что использование из разных потоков безопасно.

## Manager и QuerySet

У каждой распространённой терминальной операции есть async-близнец с префиксом
`a`:

```python
# создание / чтение
user = await User.objects.acreate(name="Ada", age=36)
user = await User.objects.aget(name="Ada")
n    = await User.objects.acount()
ok   = await User.objects.filter(active=True).aexists()
first = await User.objects.order_by("age").afirst()
last  = await User.objects.order_by("age").alast()
rows  = await User.objects.filter(age__gte=18).alist()

# асинхронная итерация
async for user in User.objects.order_by("name"):
    ...

# запись
await User.objects.all().aupdate(active=True)
await User.objects.filter(spam=True).adelete()
await User.objects.abulk_create([User(name="a"), User(name="b")])
await User.objects.abulk_update(users, ["age"])

# хелперы
user, created = await User.objects.aget_or_create(name="Ada", defaults={"age": 36})
stats = await User.objects.aaggregate(total=Count("*"))
```

## Экземпляры

```python
user = await User.objects.aget(pk=1)
user.age += 1
await user.asave()
await user.arefresh_from_db()
await user.adelete()
```

## В обработчике

```python
from endocore import Request, Response
from Models.blog import Post

async def handler(request: Request) -> Response:      # Api/v1/Post/Get.py
    posts = await Post.objects.order_by("-id").alist()
    return Response.json({"posts": [p.title for p in posts]})
```

## Транзакции

Используйте `async with aatomic():` — `a*`-вызовы внутри блока присоединяются к
транзакции (владение — токен в `contextvars`, который `asyncio.to_thread`
переносит в тредпул), а лок берётся вне event loop'а. См.
[Транзакции](transactions.md).

## Замечания

- Manager даёт async-хелперы **чтения/создания**; `aupdate`/`adelete` живут на
  **QuerySet** (вызывайте `.all().aupdate(...)`) — в соответствии с синхронной
  семантикой Django.
- Построение запроса (`filter`, `order_by`, …) дёшево и остаётся синхронным;
  в тредпул выгружается только **вычисление**.
- При высокой конкуренции настройте дефолтный тредпул (executor
  `anyio`/`asyncio`) или запустите несколько воркеров.
