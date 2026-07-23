# Relations

## ForeignKey (many-to-one)

```python
class Author(Model):
    name = fields.CharField(max_length=100)

class Book(Model):
    title  = fields.CharField(max_length=200)
    author = fields.ForeignKey(Author, related_name="books", on_delete="CASCADE")
```

Stored as a `author_id` column. Assign an instance or an id:

```python
book = Book.objects.create(title="X", author=some_author)   # or author_id=1
book.author            # lazily loads the Author (cached)
book.author_id         # the raw FK value
```

**Cross-table lookups** produce JOINs:

```python
Book.objects.filter(author__name="Ada")
Book.objects.filter(author__country__code="US")   # multi-level
Book.objects.order_by("author__name")
```

**Reverse accessor** (`related_name`, default `<model>_set`):

```python
author.books.all()                 # QuerySet of this author's books
author.books.filter(title__icontains="py")
author.books.count()
```

`on_delete` options: `CASCADE`, `SET NULL` (needs `null=True`), `RESTRICT`,
`PROTECT` (mapped to `RESTRICT` at the DB), `NO ACTION`/`DO_NOTHING`.

## OneToOneField

A unique FK — one row on each side:

```python
class Profile(Model):
    user = fields.OneToOneField(User, related_name="profile")
    bio  = fields.TextField(default="")

user.profile           # the single related Profile, or None
```

## ManyToManyField

An auto-created through table with a relation manager:

```python
class Tag(Model):
    name = fields.CharField(max_length=30)

class Post(Model):
    title = fields.CharField(max_length=200)
    tags  = fields.ManyToManyField(Tag)

post.tags.add(tag1, tag2)     # idempotent (duplicates ignored)
post.tags.remove(tag1)
post.tags.set([tag2, tag3])   # replace the set
post.tags.clear()
post.tags.all()               # QuerySet of related Tags
post.tags.count()
```

`create_all(...)` builds through tables in a second pass, so relation order
doesn't matter.

## Avoiding N+1: select_related & prefetch_related

**`select_related`** — for forward FK / OneToOne — fetches related rows in the
**same query** via a JOIN:

```python
for book in Book.objects.select_related("author"):
    book.author.name        # no extra query
Book.objects.select_related("author__country")   # multi-level
```

**`prefetch_related`** batch-loads a relation for a whole page of results
instead of one query per row — but check which relation kinds it actually
supports before reaching for it, since the two supported kinds cost
different numbers of queries:

```python
for post in Post.objects.prefetch_related("tags"):
    post.tags.all()         # served from cache, no per-row query
```

- **A `ManyToManyField` name** (like `"tags"` above) — **two** extra queries
  total: one against the through table (grouping target ids by source id),
  then one against the target model (`pk__in=[...]`) to fetch the actual
  rows. Still a huge win over N+1, just not literally "one" query.
- **A forward `ForeignKey` field's own name** (not its `related_name`) —
  **one** extra query (`pk__in=[...]` on the target model). Equivalent to
  `select_related` for that same field, except it stays a separate SELECT
  instead of a JOIN — usually you'd reach for `select_related` on a forward
  FK instead, but `prefetch_related` works too if you'd rather avoid the
  JOIN's duplicated base-table columns.
- **A reverse relation name** (`related_name`, or `<model>_set` if none was
  set) — **one** extra query (`fk__in=[...]` on the *source* model, grouped
  by fk id in Python):

```python
for author in Author.objects.prefetch_related("books"):
    author.books.all()      # served from cache — no per-author query
    list(author.books)      # plain iteration is cached too
    author.books.filter(title__startswith="A")  # chaining still re-queries
```

  Only a bare `.all()` (or iterating the relation directly, with no other
  clause) reads from the cache — anything chained afterwards
  (`.filter()`, `.exclude()`, `.order_by()`, ...) is a genuinely different
  query and always hits the database, exactly like an ordinary QuerySet.
  `.count()` on the reverse relation also always queries fresh (it doesn't
  consult the prefetch cache, the same as any other QuerySet's `.count()`)
  — if per-row counting is the actual bottleneck, `annotate(n=Count("books"))`
  avoids that instead (see [Queries](queries.md)).

## Referencing models by name

Forward references (a model defined later, or self-references) can use a string
once the class exists at call time — but the plain class reference is preferred:

```python
class Node(Model):
    parent = fields.ForeignKey("Node", null=True, related_name="children")
```
