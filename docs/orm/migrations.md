# Migrations

When your models change, the database tables have to change with them.
Migrations record each change as a file you can apply, inspect, and undo — so
the schema evolves in controlled steps instead of by hand.

Each migration is a JSON file holding the SQL to apply (`forward`), the SQL to
undo it (`reverse`), and a snapshot of the resulting schema.

## Workflow

```bash
end makemigrations initial     # write migrations/0001_initial.json from your models
end migrate                    # apply pending migrations
end showmigrations             # [x] applied  /  [ ] pending
end sqlmigrate 0001            # print a migration's forward SQL
end migrate 0002               # apply up to (and including) 0002
end rollback                   # undo the most recent migration
end rollback --steps 2         # undo the last two
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
end makemigrations rename_fullname --rename user.fullname=name
```

This emits `ALTER TABLE "user" RENAME COLUMN "fullname" TO "name"` (and the
reverse), works on SQLite (≥ 3.25) and PostgreSQL, and preserves data.

## Programmatic API

```python
from endocore.orm import Migrator, get_models

m = Migrator(get_models())              # or Migrator([Post, Author])
m.makemigrations("initial")
m.migrate()
m.showmigrations()                      # [("0001_initial", True), ...]
m.rollback(steps=1)
```

## Scope (beta)

- Data migrations and complex column transforms are out of scope — write a
  one-off script or a manual SQL migration for those.
- Migrations are generated for your project's configured **dialect**; regenerate
  if you switch backends.

!!! tip "Prototyping"
    For quick prototypes you can skip migrations and call
    `create_all(*models)` — but use migrations for anything that evolves.
