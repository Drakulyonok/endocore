# Fields

All fields import from `endocore.orm.fields`.

## Common options

Every field accepts:

| Option | Default | Meaning |
|--------|---------|---------|
| `primary_key` | `False` | mark as the primary key |
| `null` | `False` | allow `NULL` |
| `default` | — | value or zero-arg callable |
| `unique` | `False` | `UNIQUE` constraint |
| `db_column` | field name | override the column name |
| `db_index` | `False` | create an index on this column |
| `choices` | — | allowed values (validated on write) |
| `validators` | — | extra `callable(value)` validators |

## Numeric

```python
fields.AutoField()               # auto-increment PK (added automatically)
fields.BigAutoField()            # 64-bit auto PK
fields.IntegerField(default=0)
fields.SmallIntegerField()       # -32768..32767 (validated)
fields.BigIntegerField()
fields.PositiveIntegerField()    # >= 0
fields.PositiveSmallIntegerField()
fields.PositiveBigIntegerField()
fields.FloatField()
fields.DecimalField(max_digits=10, decimal_places=2)   # exact -> Decimal
```

## Text

```python
fields.CharField(max_length=100)     # VARCHAR(n), length validated
fields.TextField()
fields.SlugField(max_length=50)      # letters/numbers/-/_ (validated)
fields.EmailField()                  # email format (validated)
fields.URLField()                    # http(s) URL (validated)
fields.GenericIPAddressField()       # IPv4/IPv6 (validated)
```

## Boolean, date & time

```python
fields.BooleanField(default=False)
fields.DateField()
fields.DateTimeField(auto_now_add=True)   # set on insert
fields.DateTimeField(auto_now=True)       # set on every save
fields.TimeField()
fields.DurationField()               # timedelta, stored as microseconds
```

## Structured

```python
fields.UUIDField(default=uuid.uuid4)  # UUID; stored as CHAR(32)/native UUID
fields.JSONField(default=dict)        # dict/list; JSONB on Postgres
fields.BinaryField()                  # bytes; BLOB/BYTEA
```

## Relations

```python
fields.ForeignKey(Author, on_delete="CASCADE", related_name="books", null=True)
fields.OneToOneField(User, related_name="profile")
fields.ManyToManyField(Tag)                    # auto through table
```

`on_delete` accepts `CASCADE`, `SET NULL`, `RESTRICT`, `PROTECT`,
`NO ACTION`/`DO_NOTHING`. See [Relations](relations.md).

## Files

```python
fields.FileField(upload_to="docs")   # encrypted at rest — see Files guide
```

## Per-dialect types

The same field maps to the right column type per backend, e.g.:

| Field | SQLite | PostgreSQL |
|-------|--------|------------|
| `BooleanField` | `INTEGER` | `BOOLEAN` |
| `JSONField` | `TEXT` | `JSONB` |
| `UUIDField` | `CHAR(32)` | `UUID` |
| `DateTimeField` | `TEXT` | `TIMESTAMP` |
| `DecimalField` | `DECIMAL(p,s)` (text-preserved) | `NUMERIC(p,s)` |
| `BinaryField` | `BLOB` | `BYTEA` |

Adaptation to/from Python (e.g. `Decimal`, `datetime`, `UUID`, `dict`) is handled
by each field's `to_db` / `to_python`.
