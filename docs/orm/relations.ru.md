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

**`prefetch_related`** — для M2M и обратных связей — делает **один
дополнительный батчевый запрос** и кэширует результаты:

```python
for post in Post.objects.prefetch_related("tags"):
    post.tags.all()         # из кэша, без запроса на каждую строку
```

## Ссылки на модели по имени

Опережающие ссылки (модель, объявленная позже, или ссылка на себя) могут быть
строкой — лишь бы класс существовал к моменту вызова; но прямая ссылка на класс
предпочтительнее:

```python
class Node(Model):
    parent = fields.ForeignKey("Node", null=True, related_name="children")
```
