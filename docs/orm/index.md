# The ORM

An ORM lets you work with database tables as Python classes: you define a
model, call methods on it, and get rows back as objects — no hand-written SQL.

EndoCore's ORM is small, secure and Django-flavoured, works with **SQLite** and
**PostgreSQL**, sync and async, with relations, migrations and encrypted files.

## Security first

This is the point of the ORM. Every query is built so that:

- **Values are always bound by the driver** — never string-formatted into SQL.
- **Identifiers** (tables/columns) are validated (`^[A-Za-z_]\w*$`) and quoted.
- **Lookups are a strict whitelist** — an unknown lookup raises, never falls
  through to raw SQL.
- **`LIKE` wildcards** in user input are escaped with an `ESCAPE` clause.
- **`LIMIT`/`OFFSET`** are coerced to integers.

There are explicit injection tests in the suite proving hostile input can't
escape parameter binding.

## 60-second tour

```python
from endocore.orm import Model, fields, configure, create_all, Q, F, Count

class User(Model):
    class Meta:
        ordering = ["name"]
    name   = fields.CharField(max_length=100)
    age    = fields.IntegerField(default=0)
    active = fields.BooleanField(default=True)

configure(backend="sqlite", database="app.db")     # or backend="postgres", host=..., dbname=..., pool_size=10
create_all(User)

# create
User.objects.create(name="Ada", age=36)
User.objects.bulk_create([User(name="Bo"), User(name="Cy")])

# query (lazy, chainable)
User.objects.filter(age__gte=18).order_by("-age")
User.objects.filter(Q(age__lt=18) | Q(name__icontains="a"))
User.objects.exclude(active=False).values_list("name", flat=True)

# get / first / count / exists
User.objects.get(name="Ada")            # -> instance or User.DoesNotExist
User.objects.filter(active=True).count()

# update / F expressions / delete
User.objects.filter(active=True).update(age=F("age") + 1)
User.objects.filter(name="Bo").delete()

# aggregate
User.objects.aggregate(total=Count("*"))

# async (non-blocking for ASGI)
await User.objects.aget(name="Ada")
```

## Sections

<div class="grid cards" markdown>

- [**Models**](models.md) — declaring models, `Meta`, inheritance, instances.
- [**Fields**](fields.md) — every field type, validation, defaults.
- [**Queries**](queries.md) — filtering, lookups, `Q`, `F`, aggregates, `only`/`defer`.
- [**Relations**](relations.md) — FK, OneToOne, ManyToMany, `select_related`, `prefetch_related`.
- [**Async**](async.md) — the non-blocking API for ASGI handlers.
- [**Migrations**](migrations.md) — make/migrate/rollback, alter & rename.
- [**Transactions**](transactions.md) — `atomic()` and savepoints.
- [**Files**](files.md) — the encrypted `FileField`.

</div>

## Configuring a connection

```python
from endocore.orm import configure

# SQLite (stdlib, nothing to install)
configure(backend="sqlite", database="app.db")     # or ":memory:"

# PostgreSQL (pip install "endocore[postgres]")
configure(backend="postgres", host="localhost", dbname="app",
          user="postgres", password="secret", port=5432)
```

`configure()` registers the **default** connection lazily (it opens on first
use). Multiple connections are supported via `alias=`.
