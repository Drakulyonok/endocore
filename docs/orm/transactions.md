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

## How writes commit outside `atomic()`

Outside an `atomic()` block, each write (`save`, `create`, queryset
`update`/`delete`, `bulk_*`) commits immediately. Inside a block, commit is
deferred to the outermost `atomic()` exit.

## Concurrency notes

- The connection is guarded by a lock, so it's safe to touch from the async
  threadpool. It is **not** a connection pool — for high write concurrency, run
  multiple worker processes.
- SQLite is single-writer by nature; PostgreSQL handles concurrent writers well.
