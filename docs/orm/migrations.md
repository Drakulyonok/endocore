# Migrations

When your models change, the database tables have to change with them.
Migrations record each change as a file you can apply, inspect, and undo — so
the schema evolves in controlled steps instead of by hand.

Each migration is a JSON file holding the SQL to apply (`forward`), the SQL to
undo it (`reverse`), and a snapshot of the resulting schema.

## Workflow

```bash
endo makemigrations initial     # write migrations/0001_initial.json from your models
endo migrate                    # apply pending migrations
endo showmigrations             # [x] applied  /  [ ] pending
endo sqlmigrate 0001            # print a migration's forward SQL
endo migrate 0002               # apply up to (and including) 0002
endo rollback                   # undo the most recent migration
endo rollback --steps 2         # undo the last two
```

Migrations record themselves in an `endocore_migrations` table, so `migrate` is
idempotent.

## What it detects

- **Create / drop tables** (including M2M through tables).
- **Add / drop columns** (`ALTER TABLE ... ADD/DROP COLUMN`).
- **Create / drop indexes** (from `db_index`, FKs, and `Meta.indexes`).
- **Altered columns** (type/null change) → a portable **table rebuild**: create a
  new table with the new schema, copy data, drop the old, rename into place.
  Data is preserved and the change is reversible.

## Column renames

Auto-detecting a rename vs. a drop+add is ambiguous, so renames are **explicit**:

```bash
endo makemigrations rename_fullname --rename user.fullname=name
```

This emits `ALTER TABLE "user" RENAME COLUMN "fullname" TO "name"` (and the
reverse), works on SQLite (≥ 3.25) and PostgreSQL, and preserves data.

## Data migrations

Schema migrations are diffed automatically; data transformations (backfilling
a new column, reshaping a JSON blob, merging rows) aren't something to diff —
write one as a Python file instead of a one-off script:

```bash
endo makemigrations backfill_slugs --python   # writes migrations/0003_backfill_slugs.py
```

```python
# migrations/0003_backfill_slugs.py
def forward(conn) -> None:
    from Models.post import Post
    for post in Post.objects.all():
        post.slug = post.title.lower().replace(" ", "-")
        post.save()


def reverse(conn) -> None:
    raise NotImplementedError("this data migration cannot be reversed")
```

It's numbered into the *same* history as schema migrations — `migrate`,
`rollback`, and `showmigrations` all see it and apply it in order, instead of
a script you have to remember to run at the right point relative to a schema
change it depends on. `forward`/`reverse` run inside their own `atomic()`
block, so a raised exception rolls back any writes already made and the
migration is not recorded as applied. Import and use your models directly —
by the time a migration runs, the app is already configured. Omit `reverse`
(or raise, as the generated stub does) for a migration that can't be undone;
`rollback` then fails loudly instead of silently doing nothing.

## Programmatic API

```python
from endocore.orm import Migrator, get_models

m = Migrator(get_models())              # or Migrator([Post, Author])
m.makemigrations("initial")
m.makedatamigration("backfill_slugs")   # writes an empty forward()/reverse() stub
m.migrate()
m.showmigrations()                      # [("0001_initial", True), ...]
m.rollback(steps=1)
```

## Scope (beta)

- Column type transforms beyond a rebuild (e.g. splitting one column into two)
  still need a data migration alongside the schema one.
- Migrations are generated for your project's configured **dialect**; regenerate
  if you switch backends.

!!! tip "Prototyping"
    For quick prototypes you can skip migrations and call
    `create_all(*models)` — but use migrations for anything that evolves.
