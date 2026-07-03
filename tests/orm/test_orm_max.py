"""Reverse relations, annotate, only/defer, bulk_update."""

from __future__ import annotations

import pytest

from endocore.orm import Model, fields, configure, create_all, Count, Sum
from endocore.orm.connection import get_connection


class Author(Model):
    name = fields.CharField(max_length=50)


class Profile(Model):
    author = fields.OneToOneField(Author, related_name="profile")
    bio = fields.TextField(default="")


class Tag(Model):
    name = fields.CharField(max_length=20)


class Book(Model):
    title = fields.CharField(max_length=50)
    price = fields.IntegerField(default=0)
    author = fields.ForeignKey(Author, null=True, default=None, related_name="books")
    tags = fields.ManyToManyField(Tag)


@pytest.fixture()
def db():
    configure(backend="sqlite", database=":memory:")
    create_all(Author, Profile, Tag, Book)
    yield
    get_connection().close()


def _seed(db):
    a1 = Author.objects.create(name="Ann")
    a2 = Author.objects.create(name="Bob")
    t1 = Tag.objects.create(name="py")
    t2 = Tag.objects.create(name="web")
    b1 = Book.objects.create(title="A", price=10, author=a1)
    b1.tags.add(t1, t2)
    b2 = Book.objects.create(title="B", price=20, author=a1)
    b2.tags.add(t1)
    Book.objects.create(title="C", price=30, author=a2)
    return a1, a2, b1, b2


# -- reverse relations -------------------------------------------------------

def test_reverse_fk_manager(db):
    a1, a2, *_ = _seed(db)
    assert sorted(b.title for b in a1.books.all()) == ["A", "B"]
    assert a1.books.count() == 2
    assert a2.books.count() == 1


def test_reverse_fk_is_queryset(db):
    a1, *_ = _seed(db)
    assert sorted(b.title for b in a1.books.filter(price__gte=15)) == ["B"]


def test_reverse_one_to_one(db):
    a1, *_ = _seed(db)
    Profile.objects.create(author=a1, bio="hi")
    assert a1.profile.bio == "hi"


def test_reverse_one_to_one_missing(db):
    a1, *_ = _seed(db)
    assert a1.profile is None


# -- annotate ----------------------------------------------------------------

def test_annotate_reverse_fk_count(db):
    _seed(db)
    result = {a.name: a.n for a in Author.objects.annotate(n=Count("books")).order_by("name")}
    assert result == {"Ann": 2, "Bob": 1}


def test_annotate_m2m_count(db):
    _seed(db)
    result = {b.title: b.ntags for b in Book.objects.annotate(ntags=Count("tags")).order_by("title")}
    assert result == {"A": 2, "B": 1, "C": 0}


def test_annotate_own_field_sum(db):
    _seed(db)
    rows = list(Book.objects.annotate(s=Sum("price")).order_by("title"))
    assert rows[0].s == 10  # grouped by pk -> the row's own price


def test_annotate_with_filter(db):
    _seed(db)
    result = {a.name: a.n for a in Author.objects.filter(name="Ann").annotate(n=Count("books"))}
    assert result == {"Ann": 2}


def test_annotate_unknown_raises(db):
    from endocore.orm.exceptions import FieldError

    _seed(db)
    with pytest.raises(FieldError):
        list(Author.objects.annotate(n=Count("nonexistent")))


# -- only / defer ------------------------------------------------------------

def test_only(db):
    _, _, b1, _ = _seed(db)
    obj = Book.objects.only("title").get(pk=b1.pk)
    assert obj.title == "A"
    assert obj.price == 0  # deferred -> default


def test_defer(db):
    _, _, b1, _ = _seed(db)
    obj = Book.objects.defer("price").get(pk=b1.pk)
    assert obj.title == "A"
    assert obj.pk == b1.pk


@pytest.mark.parametrize("fields_arg", [("title",), ("title", "price")])
def test_only_various(db, fields_arg):
    _, _, b1, _ = _seed(db)
    obj = Book.objects.only(*fields_arg).get(pk=b1.pk)
    assert obj.title == "A"


# -- bulk_update -------------------------------------------------------------

def test_bulk_update(db):
    _, _, b1, b2 = _seed(db)
    b1.price = 111
    b2.price = 222
    changed = Book.objects.bulk_update([b1, b2], ["price"])
    assert changed == 2
    assert Book.objects.get(pk=b1.pk).price == 111
    assert Book.objects.get(pk=b2.pk).price == 222


def test_bulk_update_empty(db):
    assert Book.objects.bulk_update([], ["price"]) == 0
