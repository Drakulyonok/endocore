# Transactions

Wrap a block of writes so they commit together or roll back together.

```python
from endocore.orm import atomic

with atomic():
    account.balance -= 100
    account.save()
    ledger = Ledger.objects.create(amount=-100)
    # commits on clean exit; rolls back if an exception propagates
```

If the block raises, everything inside is rolled back and the exception
propagates.

## Nested blocks use savepoints

An inner `atomic()` becomes a **SAVEPOINT**, so you can catch an inner failure
and keep the outer transaction's earlier work:

```python
with atomic():
    do_a()                      # part of the outer transaction
    try:
        with atomic():          # SAVEPOINT
            do_b()              # fails
    except SomeError:
        pass                    # rolled back to the savepoint; do_a() survives
    do_c()
# outer commits: do_a() and do_c() persisted, do_b() rolled back
```

## Per-alias

```python
from endocore.orm import atomic
with atomic("default"):         # a specific connection alias
    ...
```

## Async code: `aatomic()`

In an async handler use the async twin — it acquires the transaction lock in a
worker thread, so a contended lock never blocks the event loop:

```python
from endocore.orm import aatomic

async def handler(request):
    async with aatomic():
        acc = await Account.objects.aget(pk=1)
        acc.balance -= 100
        await acc.asave()
        await Ledger.objects.acreate(amount=-100)
    # commits on clean exit; rolls back if an exception propagates
```

`a*` calls made inside the block **join the transaction**: transaction
ownership is tracked with a `contextvars` token, and `asyncio.to_thread`
propagates it into the threadpool. Nested `aatomic()` blocks become SAVEPOINTs,
same as `atomic()`. (Run the `a*` calls of one transaction sequentially — don't
`gather` them.)

Calling plain `with atomic():` on the event loop thread emits a
`RuntimeWarning`: if the lock is contended it would block the whole loop.

## How writes commit outside `atomic()`

Outside an `atomic()` block, each write (`save`, `create`, queryset
`update`/`delete`, `bulk_*`) commits immediately. Inside a block, commit is
deferred to the outermost `atomic()` exit.

## Concurrency notes

- A transaction **pins one pooled connection** for its whole block, so
  concurrent requests can never interleave statements inside it.
- Each alias owns a small connection pool: `configure(..., pool_size=N)`
  (defaults: SQLite 1, PostgreSQL 5). With SQLite's pool of 1, transactions
  serialize and autocommit writes wait out the open transaction; with
  PostgreSQL, up to `pool_size` transactions run truly concurrently.
- SQLite is single-writer by nature; PostgreSQL handles concurrent writers well.
