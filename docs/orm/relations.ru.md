# Связи

## ForeignKey (многие-к-одному)

```python
class Author(Model):
    name = fields.CharField(max_length=100)

class Book(Model):
    title  = fields.CharField(max_length=200)
    author = fields.ForeignKey(Author, related_name="books", on_delete="CASCADE")
```

Хранится как колонка `author_id`. Присваивать можно экземпляр или id:

```python
book = Book.objects.create(title="X", author=some_author)   # или author_id=1
book.author            # лениво загружает Author (кэшируется)
book.author_id         # сырое значение FK
```

**Кросс-табличные lookup'ы** порождают JOIN'ы:

```python
Book.objects.filter(author__name="Ada")
Book.objects.filter(author__country__code="US")   # многоуровневый
Book.objects.order_by("author__name")
```

**Обратный аксессор** (`related_name`, по умолчанию `<model>_set`):

```python
author.books.all()                 # QuerySet книг этого автора
author.books.filter(title__icontains="py")
author.books.count()
```

Варианты `on_delete`: `CASCADE`, `SET NULL` (нужен `null=True`), `RESTRICT`,
`PROTECT` (на уровне БД отображается в `RESTRICT`), `NO ACTION`/`DO_NOTHING`.

## OneToOneField

Уникальный FK — по одной записи с каждой стороны:

```python
class Profile(Model):
    user = fields.OneToOneField(User, related_name="profile")
    bio  = fields.TextField(default="")

user.profile           # единственный связанный Profile или None
```

## ManyToManyField

Автоматически создаваемая through-таблица с менеджером связи:

```python
class Tag(Model):
    name = fields.CharField(max_length=30)

class Post(Model):
    title = fields.CharField(max_length=200)
    tags  = fields.ManyToManyField(Tag)

post.tags.add(tag1, tag2)     # идемпотентно (дубли игнорируются)
post.tags.remove(tag1)
post.tags.set([tag2, tag3])   # заменить множество
post.tags.clear()
post.tags.all()               # QuerySet связанных Tag'ов
post.tags.count()
```

`create_all(...)` строит through-таблицы вторым проходом, поэтому порядок
объявления связей не важен.

## Избегаем N+1: select_related и prefetch_related

**`select_related`** — для прямых FK / OneToOne — достаёт связанные строки в
**том же запросе** через JOIN:

```python
for book in Book.objects.select_related("author"):
    book.author.name        # без дополнительного запроса
Book.objects.select_related("author__country")   # многоуровневый
```

**`prefetch_related`** батчево подгружает связь для целой страницы
результатов вместо запроса на каждую строку — но прежде чем тянуться за ним,
проверьте, какие виды связей он реально поддерживает: два поддерживаемых
вида стоят разного числа запросов:

```python
for post in Post.objects.prefetch_related("tags"):
    post.tags.all()         # из кэша, без запроса на каждую строку
```

- **Имя поля `ManyToManyField`** (как `"tags"` выше) — **два**
  дополнительных запроса всего: один к through-таблице (группирует id целей
  по id источника), затем один к целевой модели (`pk__in=[...]`), чтобы
  забрать сами строки. Всё равно огромный выигрыш по сравнению с N+1, просто
  не буквально «один» запрос.
- **Собственное имя поля прямого `ForeignKey`** (не его `related_name`) —
  **один** дополнительный запрос (`pk__in=[...]` к целевой модели).
  Эквивалентно `select_related` для того же поля, только остаётся отдельным
  SELECT'ом вместо JOIN'а — обычно для прямого FK тянутся именно к
  `select_related`, но `prefetch_related` тоже работает, если хочется
  избежать задвоенных колонок базовой таблицы из JOIN'а.

**Обратные связи (`related_name`, `<model>_set`) `prefetch_related` НЕ
поддерживает** — `Author.objects.prefetch_related("books")` поднимет
`FieldError: 'books' is not a relation on Author`, потому что резолвер
распознаёт только имена полей M2M и прямых FK, но не обратные аксессоры.
Сейчас нет батчевого способа избежать N+1 на обратной стороне
`ForeignKey` — `author.books.all()` всегда делает отдельный запрос на
каждого автора. Если это реальное узкое место, `annotate(n=Count("books"))`
хотя бы избегает запросов на *подсчёт* по каждой строке (см.
[Запросы](queries.md)), хотя сами связанные строки он не забирает.

## Ссылки на модели по имени

Опережающие ссылки (модель, объявленная позже, или ссылка на себя) могут быть
строкой — лишь бы класс существовал к моменту вызова; но прямая ссылка на класс
предпочтительнее:

```python
class Node(Model):
    parent = fields.ForeignKey("Node", null=True, related_name="children")
```
