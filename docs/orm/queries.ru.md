# Запросы

`Model.objects` — менеджер, выдающий **QuerySet'ы** — ленивые, чейнящиеся
построители, которые обращаются к базе только при вычислении (итерация,
`list()`, `len()`, срез с концом, `.get()`, `.count()`, …).

## Выборка

```python
User.objects.all()
User.objects.filter(active=True)
User.objects.exclude(role="admin")
User.objects.filter(active=True).exclude(age__lt=18)   # цепочка = AND

User.objects.get(pk=1)                 # ровно один, иначе DoesNotExist / MultipleObjectsReturned
User.objects.first()                   # первый или None (учитывает сортировку)
User.objects.last()
User.objects.count()
User.objects.exists()
User.objects.filter(pk__in=[1, 2, 3]).in_bulk([1, 2, 3])   # {pk: obj}
```

## Lookup'ы полей

`field__lookup=value`:

| Lookup | SQL |
|--------|-----|
| `exact` (по умолчанию) | `= ?` (или `IS NULL`) |
| `iexact` | `=` без учёта регистра |
| `contains` / `icontains` | `LIKE %v%` (i = без учёта регистра) |
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

!!! note "Консистентный LIKE"
    На SQLite `LIKE` делается регистрозависимым (`PRAGMA case_sensitive_like`),
    поэтому `contains` и `icontains` ведут себя так же, как на PostgreSQL.

## Q-объекты — OR / NOT / группировка

```python
from endocore.orm import Q

User.objects.filter(Q(age__lt=18) | Q(age__gt=65))
User.objects.filter(Q(active=True) & ~Q(role="admin"))
User.objects.filter(Q(name__icontains="a"), active=True)   # Q AND kwargs
```

## Сортировка, срезы, distinct

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

## F-выражения и агрегаты

```python
from endocore.orm import F, Count, Sum, Avg, Min, Max

# атомарная арифметика на стороне БД (по-прежнему параметризованная)
Post.objects.filter(id=1).update(views=F("views") + 1)

Post.objects.aggregate(total=Sum("views"), n=Count("*"), avg=Avg("views"))
```

## annotate()

Прикрепить к каждой строке агрегат по полю, M2M или обратному FK:

```python
Author.objects.annotate(n=Count("books"))     # счётчик по обратному FK
Book.objects.annotate(ntags=Count("tags"))     # счётчик по M2M
for a in Author.objects.annotate(n=Count("books")):
    print(a.name, a.n)
```

## only() / defer()

Выбрать подмножество колонок (остальные по умолчанию `None`):

```python
Book.objects.only("title")           # SELECT id, title
Book.objects.defer("body")           # SELECT всё, кроме body
```

## Массовая запись

```python
User.objects.bulk_create([User(name="a"), User(name="b")])     # один INSERT
User.objects.bulk_update(users, ["name", "age"])               # батчевый UPDATE
User.objects.filter(active=False).update(active=True)          # UPDATE по множеству
User.objects.filter(spam=True).delete()                        # DELETE по множеству
```

`bulk_create`/`bulk_update` валидируют каждый объект точно так же, как
`save()` (обязательность, `choices`, кастомные валидаторы) — массовая запись
не получает поблажку на инварианты, которые обеспечил бы обычный `save()`.

## get_or_create / update_or_create

```python
user, created = User.objects.get_or_create(name="Ada", defaults={"age": 36})
user, created = User.objects.update_or_create(name="Ada", defaults={"age": 37})
```

Безопасно при конкурентном доступе для поля с настоящим ограничением
`unique=True`: если два вызова гонятся за одной ещё не существующей строкой,
`create()` проигравшего упирается в ограничение, и вместо исключения это
трактуется как «кто-то другой её уже создал» — строка перечитывается и
возвращается с `created=False`, как если бы она уже существовала.

## none()

Всегда пустой QuerySet, который никогда не трогает БД — удобно для условной
сборки запроса:

```python
qs = User.objects.none()
if show_all:
    qs = User.objects.all()
```
