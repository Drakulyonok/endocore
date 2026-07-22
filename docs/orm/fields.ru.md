# Поля

Все поля импортируются из `endocore.orm.fields`.

## Общие опции

Каждое поле принимает:

| Опция | По умолчанию | Значение |
|--------|---------|---------|
| `primary_key` | `False` | пометить как первичный ключ |
| `null` | `False` | разрешить `NULL` |
| `default` | — | значение или callable без аргументов |
| `unique` | `False` | ограничение `UNIQUE` |
| `db_column` | имя поля | переопределить имя колонки |
| `db_index` | `False` | создать индекс по этой колонке |
| `choices` | — | допустимые значения (проверяются при записи) |
| `validators` | — | дополнительные валидаторы `callable(value)` |

## Числовые

```python
fields.AutoField()               # автоинкрементный PK (добавляется автоматически)
fields.BigAutoField()            # 64-битный авто-PK
fields.IntegerField(default=0)
fields.SmallIntegerField()       # -32768..32767 (валидируется)
fields.BigIntegerField()
fields.PositiveIntegerField()    # >= 0
fields.PositiveSmallIntegerField()
fields.PositiveBigIntegerField()
fields.FloatField()
fields.DecimalField(max_digits=10, decimal_places=2)   # точный -> Decimal
```

## Текстовые

```python
fields.CharField(max_length=100)     # VARCHAR(n), длина валидируется
fields.TextField()
fields.SlugField(max_length=50)      # буквы/цифры/-/_ (валидируется)
fields.EmailField()                  # формат email (валидируется)
fields.URLField()                    # http(s) URL (валидируется)
fields.GenericIPAddressField()       # IPv4/IPv6 (валидируется)
```

## Логические, дата и время

```python
fields.BooleanField(default=False)
fields.DateField()
fields.DateTimeField(auto_now_add=True)   # ставится при вставке
fields.DateTimeField(auto_now=True)       # ставится при каждом save
fields.TimeField()
fields.DurationField()               # timedelta, хранится в микросекундах
```

## Структурные

```python
fields.UUIDField(default=uuid.uuid4)  # UUID; хранится как CHAR(32)/нативный UUID
fields.JSONField(default=dict)        # dict/list; JSONB на Postgres
fields.BinaryField()                  # bytes; BLOB/BYTEA
```

## Связи

```python
fields.ForeignKey(Author, on_delete="CASCADE", related_name="books", null=True)
fields.OneToOneField(User, related_name="profile")
fields.ManyToManyField(Tag)                    # автоматическая through-таблица
```

`on_delete` принимает `CASCADE`, `SET NULL`, `RESTRICT`, `PROTECT`,
`NO ACTION`/`DO_NOTHING`. См. [Связи](relations.md).

## Файлы

```python
fields.FileField(upload_to="docs")   # шифруется на диске — см. гайд «Файлы»
```

## Типы по диалектам

Одно и то же поле отображается в правильный тип колонки для каждого бэкенда,
например:

| Поле | SQLite | PostgreSQL |
|-------|--------|------------|
| `BooleanField` | `INTEGER` | `BOOLEAN` |
| `JSONField` | `TEXT` | `JSONB` |
| `UUIDField` | `CHAR(32)` | `UUID` |
| `DateTimeField` | `TEXT` | `TIMESTAMP` |
| `DecimalField` | `DECIMAL(p,s)` (хранится текстом без потерь) | `NUMERIC(p,s)` |
| `BinaryField` | `BLOB` | `BYTEA` |

Преобразование в Python и обратно (например `Decimal`, `datetime`, `UUID`,
`dict`) выполняют методы `to_db` / `to_python` каждого поля.
