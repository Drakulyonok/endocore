# Models

A model is a Python class describing one table.

```python
from endocore.orm import Model, fields

class Article(Model):
    title     = fields.CharField(max_length=200)
    body      = fields.TextField(default="")
    published = fields.BooleanField(default=False)
    created   = fields.DateTimeField(auto_now_add=True)
```

- A primary key is added automatically as `id = AutoField()` unless you declare
  one (`primary_key=True` on a field, or an `AutoField`/`BigAutoField`).
- The table name defaults to the lower-cased class name (`article`).

## Meta options

```python
class Article(Model):
    class Meta:
        table = "articles"                    # override table name
        ordering = ["-created"]               # default order for queries
        unique_together = ("author", "slug")  # composite UNIQUE
        indexes = [["author", "created"]]      # composite index
        abstract = False

    author  = fields.ForeignKey("Author")
    slug    = fields.SlugField()
    created = fields.DateTimeField(auto_now_add=True)
```

| Option | Meaning |
|--------|---------|
| `table` | database table name |
| `ordering` | default `order_by` when a query has none |
| `unique_together` | `("a","b")` or `(("a","b"),("c","d"))` → `UNIQUE(...)` |
| `indexes` | list of column-name lists → composite `CREATE INDEX` |
| `abstract` | `True` → no table; fields are inherited by subclasses |

## Abstract base models

Share columns across models without a table of their own:

```python
class TimeStamped(Model):
    class Meta:
        abstract = True
    created = fields.DateTimeField(auto_now_add=True)
    updated = fields.DateTimeField(auto_now=True)

class Post(TimeStamped):          # inherits created/updated
    title = fields.CharField(max_length=200)
```

## Instances

```python
a = Article(title="Hi")          # not saved yet; pk is None
a.title = "Hello"
a.save()                         # INSERT -> pk assigned
a.published = True
a.save(update_fields=["published"])   # UPDATE only that column

a.refresh_from_db()              # reload values
a.delete()                       # DELETE; pk set back to None
```

- `Model.objects.create(**kwargs)` builds + saves in one step.
- `save()` inserts when `pk is None`, otherwise updates.
- `save(update_fields=[...])` writes only those columns.
- Equality/`hash` are by primary key; two saved rows with the same pk are equal.

## Validation

Field validation runs on the write path (`save`/`create`/`update`):

```python
from endocore.orm import ValidationError

class User(Model):
    email = fields.EmailField()
    role  = fields.CharField(max_length=10, choices=["admin", "user"])

try:
    User.objects.create(email="not-an-email", role="ghost")
except ValidationError as exc:
    ...
```

`full_clean()` runs all validators manually. See [Fields](fields.md) for what
each field validates.

## The model registry

Every concrete model registers itself; migrations and tooling use it:

```python
from endocore.orm import get_models
get_models()          # -> [Article, User, ...]
```
