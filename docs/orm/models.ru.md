# Модели

Модель — это Python-класс, описывающий одну таблицу.

```python
from endocore.orm import Model, fields

class Article(Model):
    title     = fields.CharField(max_length=200)
    body      = fields.TextField(default="")
    published = fields.BooleanField(default=False)
    created   = fields.DateTimeField(auto_now_add=True)
```

- Первичный ключ добавляется автоматически как `id = AutoField()`, если вы не
  объявили свой (`primary_key=True` на поле, либо `AutoField`/`BigAutoField`).
- Имя таблицы по умолчанию — имя класса в нижнем регистре (`article`).

## Опции Meta

```python
class Article(Model):
    class Meta:
        table = "articles"                    # переопределить имя таблицы
        ordering = ["-created"]               # порядок по умолчанию для запросов
        unique_together = ("author", "slug")  # составной UNIQUE
        indexes = [["author", "created"]]      # составной индекс
        abstract = False

    author  = fields.ForeignKey("Author")
    slug    = fields.SlugField()
    created = fields.DateTimeField(auto_now_add=True)
```

| Опция | Значение |
|--------|---------|
| `table` | имя таблицы в базе |
| `ordering` | `order_by` по умолчанию, если у запроса его нет |
| `unique_together` | `("a","b")` или `(("a","b"),("c","d"))` → `UNIQUE(...)` |
| `indexes` | список списков колонок → составной `CREATE INDEX` |
| `abstract` | `True` → без таблицы; поля наследуются подклассами |

## Абстрактные базовые модели

Общие колонки для нескольких моделей без собственной таблицы:

```python
class TimeStamped(Model):
    class Meta:
        abstract = True
    created = fields.DateTimeField(auto_now_add=True)
    updated = fields.DateTimeField(auto_now=True)

class Post(TimeStamped):          # наследует created/updated
    title = fields.CharField(max_length=200)
```

## Экземпляры

```python
a = Article(title="Hi")          # ещё не сохранён; pk = None
a.title = "Hello"
a.save()                         # INSERT -> pk присвоен
a.published = True
a.save(update_fields=["published"])   # UPDATE только этой колонки

a.refresh_from_db()              # перечитать значения
a.delete()                       # DELETE; pk снова None
```

- `Model.objects.create(**kwargs)` создаёт и сохраняет за один шаг.
- `save()` делает INSERT, когда `pk is None`, иначе — UPDATE.
- `save(update_fields=[...])` пишет только указанные колонки.
- Равенство/`hash` — по первичному ключу; две сохранённые записи с одним pk
  равны.

## Валидация

Валидация полей выполняется на пути записи (`save`/`create`/`update`):

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

`full_clean()` запускает все валидаторы вручную. Что валидирует каждое поле —
см. [Поля](fields.md).

## Реестр моделей

Каждая конкретная модель регистрирует себя; этим пользуются миграции и
инструменты:

```python
from endocore.orm import get_models
get_models()          # -> [Article, User, ...]
```
