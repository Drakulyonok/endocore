"""FK / OneToOne / ManyToMany / select_related / prefetch_related coverage."""

from __future__ import annotations

import pytest

from endocore.orm import Model, fields, configure, create_all
from endocore.orm.connection import get_connection


class Author(Model):
    name = fields.CharField(max_length=50)


class Profile(Model):
    author = fields.OneToOneField(Author)
    bio = fields.TextField(default="")


class Tag(Model):
    name = fields.CharField(max_length=20)


class Book(Model):
    title = fields.CharField(max_length=50)
    author = fields.ForeignKey(Author, null=True, default=None)
    tags = fields.ManyToManyField(Tag)


@pytest.fixture()
def db():
    configure(backend="sqlite", database=":memory:")
    create_all(Author, Profile, Tag, Book)
    yield
    get_connection().close()


# -- ForeignKey --------------------------------------------------------------

def test_fk_assign_instance(db):
    a = Author.objects.create(name="Ann")
    b = Book.objects.create(title="T", author=a)
    assert Book.objects.get(pk=b.pk).author_id == a.pk
    assert Book.objects.get(pk=b.pk).author.name == "Ann"


def test_fk_assign_by_id(db):
    a = Author.objects.create(name="Ann")
    b = Book.objects.create(title="T", author_id=a.pk)
    assert Book.objects.get(pk=b.pk).author.name == "Ann"


def test_fk_null(db):
    b = Book.objects.create(title="T")
    assert Book.objects.get(pk=b.pk).author is None


@pytest.mark.parametrize("n", [1, 3, 5])
def test_fk_filter(db, n):
    a = Author.objects.create(name="A")
    other = Author.objects.create(name="B")
    for i in range(n):
        Book.objects.create(title=f"t{i}", author=a)
    Book.objects.create(title="x", author=other)
    assert Book.objects.filter(author=a).count() == n
    assert Book.objects.filter(author__name="A").count() == n


# -- OneToOne ----------------------------------------------------------------

def test_one_to_one(db):
    a = Author.objects.create(name="Ann")
    p = Profile.objects.create(author=a, bio="hi")
    assert Profile.objects.get(pk=p.pk).author.name == "Ann"


def test_one_to_one_unique(db):
    a = Author.objects.create(name="Ann")
    Profile.objects.create(author=a)
    with pytest.raises(Exception):
        Profile.objects.create(author=a)  # violates UNIQUE


# -- ManyToMany --------------------------------------------------------------

@pytest.mark.parametrize("count", [0, 1, 2, 5])
def test_m2m_add_and_all(db, count):
    b = Book.objects.create(title="T")
    tags = [Tag.objects.create(name=f"t{i}") for i in range(count)]
    b.tags.add(*tags)
    assert b.tags.count() == count
    assert {t.name for t in b.tags.all()} == {f"t{i}" for i in range(count)}


def test_m2m_add_idempotent(db):
    b = Book.objects.create(title="T")
    t = Tag.objects.create(name="x")
    b.tags.add(t)
    b.tags.add(t)  # duplicate ignored
    assert b.tags.count() == 1


def test_m2m_remove(db):
    b = Book.objects.create(title="T")
    t1, t2 = Tag.objects.create(name="a"), Tag.objects.create(name="b")
    b.tags.add(t1, t2)
    b.tags.remove(t1)
    assert {t.name for t in b.tags.all()} == {"b"}


def test_m2m_set(db):
    b = Book.objects.create(title="T")
    t1, t2, t3 = (Tag.objects.create(name=n) for n in "abc")
    b.tags.add(t1)
    b.tags.set([t2, t3])
    assert {t.name for t in b.tags.all()} == {"b", "c"}


def test_m2m_clear(db):
    b = Book.objects.create(title="T")
    b.tags.add(*[Tag.objects.create(name=n) for n in "abc"])
    b.tags.clear()
    assert b.tags.count() == 0


def test_m2m_independent_per_instance(db):
    b1, b2 = Book.objects.create(title="1"), Book.objects.create(title="2")
    t = Tag.objects.create(name="shared")
    b1.tags.add(t)
    assert b1.tags.count() == 1 and b2.tags.count() == 0


# -- select_related / prefetch_related --------------------------------------

def test_select_related(db):
    a = Author.objects.create(name="Ann")
    Book.objects.create(title="T", author=a)
    book = Book.objects.select_related("author").get(title="T")
    assert book.author.name == "Ann"


@pytest.mark.parametrize("n", [1, 3, 6])
def test_prefetch_m2m(db, n):
    tags = [Tag.objects.create(name=f"t{i}") for i in range(n)]
    b = Book.objects.create(title="T")
    b.tags.add(*tags)
    Book.objects.create(title="empty")
    books = list(Book.objects.prefetch_related("tags").order_by("title"))
    by_title = {bk.title: sorted(t.name for t in bk.tags.all()) for bk in books}
    assert by_title["T"] == sorted(t.name for t in tags)
    assert by_title["empty"] == []


def test_prefetch_fk(db):
    a = Author.objects.create(name="Ann")
    for i in range(3):
        Book.objects.create(title=f"t{i}", author=a)
    books = list(Book.objects.prefetch_related("author").filter(author=a))
    assert all(bk.author.name == "Ann" for bk in books)
