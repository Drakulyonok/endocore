# Queries

`Model.objects` is a manager that hands out **QuerySets** — lazy, chainable
builders that hit the database only when evaluated (iterated, `list()`, `len()`,
sliced with a stop, `.get()`, `.count()`, …).

## Retrieving

```python
User.objects.all()
User.objects.filter(active=True)
User.objects.exclude(role="admin")
User.objects.filter(active=True).exclude(age__lt=18)   # chained = AND

User.objects.get(pk=1)                 # exactly one, else DoesNotExist / MultipleObjectsReturned
User.objects.first()                   # first or None (honours ordering)
User.objects.last()
User.objects.count()
User.objects.exists()
User.objects.filter(pk__in=[1, 2, 3]).in_bulk([1, 2, 3])   # {pk: obj}
```

## Field lookups

`field__lookup=value`:

| Lookup | SQL |
|--------|-----|
| `exact` (default) | `= ?` (or `IS NULL`) |
| `iexact` | case-insensitive `=` |
| `contains` / `icontains` | `LIKE %v%` (i = case-insensitive) |
| `startswith` / `istartswith` | `LIKE v%` |
| `endswith` / `iendswith` | `LIKE %v` |
| `gt` `gte` `lt` `lte` | `>` `>=` `<` `<=` |
| `in` | `IN (...)` |
| `range` | `BETWEEN ? AND ?` |
| `isnull` | `IS NULL` / `IS NOT NULL` |

```python
User.objects.filter(name__icontains="ada")
User.objects.filter(age__range=(18, 65))
User.objects.filter(id__in=[1, 2, 3])
User.objects.filter(deleted_at__isnull=True)
```

!!! note "Consistent LIKE"
    On SQLite, `LIKE` is made case-sensitive (`PRAGMA case_sensitive_like`) so
    `contains` and `icontains` behave identically to PostgreSQL.

## Q objects — OR / NOT / grouping

```python
from endocore.orm import Q

User.objects.filter(Q(age__lt=18) | Q(age__gt=65))
User.objects.filter(Q(active=True) & ~Q(role="admin"))
User.objects.filter(Q(name__icontains="a"), active=True)   # Q AND kwargs
```

## Ordering, slicing, distinct

```python
User.objects.order_by("name", "-age")
User.objects.order_by("name")[:10]        # LIMIT 10
User.objects.order_by("name")[10:20]      # OFFSET 10 LIMIT 10
User.objects.values_list("name", flat=True).distinct()
```

## values() / values_list()

```python
User.objects.values("id", "name")             # [{"id":1,"name":"Ada"}, ...]
User.objects.values_list("id", "name")        # [(1, "Ada"), ...]
User.objects.values_list("name", flat=True)   # ["Ada", ...]
```

## F expressions & aggregates

```python
from endocore.orm import F, Count, Sum, Avg, Min, Max

# atomic, DB-side arithmetic (still parameterized)
Post.objects.filter(id=1).update(views=F("views") + 1)

Post.objects.aggregate(total=Sum("views"), n=Count("*"), avg=Avg("views"))
```

## annotate()

Attach an aggregate over a field, a M2M, or a reverse FK to each row:

```python
Author.objects.annotate(n=Count("books"))     # reverse-FK count
Book.objects.annotate(ntags=Count("tags"))     # M2M count
for a in Author.objects.annotate(n=Count("books")):
    print(a.name, a.n)
```

## only() / defer()

Fetch a subset of columns (the rest default to `None`):

```python
Book.objects.only("title")           # SELECT id, title
Book.objects.defer("body")           # SELECT everything except body
```

## Writing in bulk

```python
User.objects.bulk_create([User(name="a"), User(name="b")])     # one INSERT
User.objects.bulk_update(users, ["name", "age"])               # batched UPDATE
User.objects.filter(active=False).update(active=True)          # set-based UPDATE
User.objects.filter(spam=True).delete()                        # set-based DELETE
```

`bulk_create`/`bulk_update` validate each object the same way `save()` does
(required-ness, `choices`, custom validators) — a bulk write doesn't get a
pass on invariants a single `save()` would have enforced.

## get_or_create / update_or_create

```python
user, created = User.objects.get_or_create(name="Ada", defaults={"age": 36})
user, created = User.objects.update_or_create(name="Ada", defaults={"age": 37})
```

Safe under concurrency for a field with a real `unique=True` constraint: if
two callers race the same not-yet-existing row, the loser's `create()` hits
the constraint, and instead of raising it's treated as "someone else just
created it" — the row is re-fetched and returned as `created=False`, same as
if it had already existed.

## none()

An always-empty QuerySet that never hits the DB — handy for conditional query
building:

```python
qs = User.objects.none()
if show_all:
    qs = User.objects.all()
```
