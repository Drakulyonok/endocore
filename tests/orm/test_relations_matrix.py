"""FK / OneToOne / ManyToMany / select_related / prefetch_related coverage."""

from __future__ import annotations

import pytest

from endocore.orm import Model, fields, configure, create_all
from endocore.orm.connection import get_connection
from endocore.orm.exceptions import FieldError


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


def test_m2m_add_bogus_target_still_raises(db):
    """The idempotent-race handling in add() must not swallow a genuinely
    invalid target — only a real duplicate-key race is silently accepted."""
    b = Book.objects.create(title="T")
    with pytest.raises(Exception, match="FOREIGN KEY|foreign key"):
        b.tags.add(999999)
    assert b.tags.count() == 0


def test_m2m_set_rolls_back_clear_on_failure(db):
    b = Book.objects.create(title="T")
    t = Tag.objects.create(name="a")
    b.tags.add(t)
    with pytest.raises(Exception):
        b.tags.set([999999])
    assert {t.name for t in b.tags.all()} == {"a"}  # clear() rolled back, not left empty


def test_m2m_add_concurrent_race_stays_idempotent(tmp_path):
    """Two add() calls racing the same (instance, target) pair must both
    succeed with exactly one through-table row — not leak the loser's
    IntegrityError past the caller (the through table's composite primary
    key is what would otherwise raise)."""
    import threading

    configure(backend="sqlite", database=str(tmp_path / "m2m_race.db"), pool_size=4)
    create_all(Author, Profile, Tag, Book)
    try:
        book = Book.objects.create(title="T")
        tag = Tag.objects.create(name="x")

        outcomes: list[str] = []
        lock = threading.Lock()
        attempts = 6
        barrier = threading.Barrier(attempts)

        def attempt():
            barrier.wait()
            try:
                book.tags.add(tag)
                outcome = "ok"
            except Exception as exc:  # noqa: BLE001
                outcome = f"error: {exc!r}"
            with lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=attempt) for _ in range(attempts)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)

        assert outcomes == ["ok"] * attempts, outcomes
        assert book.tags.count() == 1
    finally:
        get_connection().close()


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


def _count_queries(fn):
    """Run ``fn`` and return (result, number of statements sent to the DB)."""
    conn = get_connection()
    original = conn.execute
    calls = []

    def counting(sql, params=(), **kwargs):
        calls.append(sql)
        return original(sql, params, **kwargs)

    conn.execute = counting
    try:
        result = fn()
    finally:
        conn.execute = original
    return result, len(calls)


def test_prefetch_reverse_fk_all_and_iteration_hit_no_query(db):
    """``author.book_set`` is the reverse accessor here (no related_name set
    on Book.author) — prefetch_related must batch it in one extra query, and
    both ``.all()`` and plain iteration must then read from that cache."""
    a1 = Author.objects.create(name="Ada")
    a2 = Author.objects.create(name="Bo")
    Author.objects.create(name="Cy")  # no books at all
    Book.objects.create(title="X1", author=a1)
    Book.objects.create(title="X2", author=a1)
    Book.objects.create(title="Y1", author=a2)

    authors, n_prefetch = _count_queries(
        lambda: list(Author.objects.order_by("name").prefetch_related("book_set"))
    )
    assert n_prefetch == 2  # authors + the one batched books query

    by_name = {a.name: a for a in authors}

    (titles_a1, titles_a2, titles_c), n_reads = _count_queries(lambda: (
        sorted(b.title for b in by_name["Ada"].book_set.all()),
        sorted(b.title for b in by_name["Bo"].book_set.all()),
        list(by_name["Cy"].book_set.all()),
    ))
    assert n_reads == 0, "prefetched .all() must not touch the database"
    assert titles_a1 == ["X1", "X2"]
    assert titles_a2 == ["Y1"]
    assert titles_c == []

    # plain iteration (no explicit .all()) must also use the cache
    _, n_iter = _count_queries(lambda: list(by_name["Ada"].book_set))
    assert n_iter == 0


def test_prefetch_reverse_fk_filter_still_queries_fresh(db):
    """Chaining beyond the bare relation (.filter/.exclude/...) must not
    silently serve stale cached rows — it's a different query, so it has to
    actually run."""
    a = Author.objects.create(name="Ada")
    Book.objects.create(title="Xylophone", author=a)
    Book.objects.create(title="Yo-yo", author=a)

    authors, _ = _count_queries(
        lambda: list(Author.objects.filter(name="Ada").prefetch_related("book_set"))
    )
    filtered, n = _count_queries(
        lambda: list(authors[0].book_set.filter(title__startswith="X"))
    )
    assert n == 1
    assert [b.title for b in filtered] == ["Xylophone"]


def test_prefetch_reverse_fk_unknown_name_still_raises(db):
    with pytest.raises(FieldError):
        list(Author.objects.prefetch_related("no_such_relation"))
