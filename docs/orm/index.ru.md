# ORM

ORM позволяет работать с таблицами базы данных как с Python-классами: вы
описываете модель, вызываете методы и получаете строки таблиц в виде объектов —
без SQL руками.

ORM EndoCore — небольшая, безопасная, в стиле Django. Работает со **SQLite** и
**PostgreSQL**, sync и async, со связями, миграциями и зашифрованными файлами.

## Безопасность прежде всего

Это и есть смысл ORM. Каждый запрос строится так, что:

- **Значения всегда биндятся драйвером** — никогда не форматируются в SQL-строку.
- **Идентификаторы** (таблицы/колонки) валидируются (`^[A-Za-z_]\w*$`) и квотируются.
- **Операторы — строгий белый список** — неизвестный lookup выбрасывает ошибку,
  а не проваливается в сырой SQL.
- **Wildcard'ы `LIKE`** в пользовательском вводе экранируются через `ESCAPE`.
- **`LIMIT`/`OFFSET`** приводятся к целым.

В наборе есть явные тесты на инъекции, доказывающие, что враждебный ввод не может
выйти за пределы биндинга параметров.

## Тур за 60 секунд

```python
from endocore.orm import Model, fields, configure, create_all, Q, F, Count

class User(Model):
    class Meta:
        ordering = ["name"]
    name   = fields.CharField(max_length=100)
    age    = fields.IntegerField(default=0)
    active = fields.BooleanField(default=True)

configure(backend="sqlite", database="app.db")     # или backend="postgres", host=..., dbname=...
create_all(User)

# создание
User.objects.create(name="Ada", age=36)
User.objects.bulk_create([User(name="Bo"), User(name="Cy")])

# запросы (ленивые, чейнятся)
User.objects.filter(age__gte=18).order_by("-age")
User.objects.filter(Q(age__lt=18) | Q(name__icontains="a"))
User.objects.exclude(active=False).values_list("name", flat=True)

# get / first / count / exists
User.objects.get(name="Ada")            # -> объект или User.DoesNotExist
User.objects.filter(active=True).count()

# update / F-выражения / delete
User.objects.filter(active=True).update(age=F("age") + 1)
User.objects.filter(name="Bo").delete()

# агрегаты
User.objects.aggregate(total=Count("*"))

# async (неблокирующий для ASGI)
await User.objects.aget(name="Ada")
```

## Разделы

- [**Модели**](models.md) — объявление, `Meta`, наследование, инстансы.
- [**Поля**](fields.md) — все типы полей, валидация, дефолты.
- [**Запросы**](queries.md) — фильтры, lookups, `Q`, `F`, агрегаты, `only`/`defer`.
- [**Связи**](relations.md) — FK, OneToOne, ManyToMany, `select_related`, `prefetch_related`.
- [**Async**](async.md) — неблокирующий API для ASGI-хендлеров.
- [**Миграции**](migrations.md) — make/migrate/rollback, alter и rename.
- [**Транзакции**](transactions.md) — `atomic()` и сейвпоинты.
- [**Файлы**](files.md) — зашифрованный `FileField`.

## Настройка подключения

```python
from endocore.orm import configure

# SQLite (стдлиб, ставить нечего)
configure(backend="sqlite", database="app.db")     # или ":memory:"

# PostgreSQL (pip install "endocore[postgres]")
configure(backend="postgres", host="localhost", dbname="app",
          user="postgres", password="secret", port=5432)
```

`configure()` регистрирует **default**-подключение лениво (открывается при первом
использовании). Несколько подключений поддерживаются через `alias=`.
