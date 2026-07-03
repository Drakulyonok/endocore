"""Async ORM API (threadpool offload)."""

from __future__ import annotations

import asyncio

import pytest

from endocore.orm import Model, fields, configure, create_all, Count
from endocore.orm.connection import get_connection


class Item(Model):
    name = fields.CharField(max_length=20)
    n = fields.IntegerField(default=0)


@pytest.fixture()
def db():
    configure(backend="sqlite", database=":memory:")
    create_all(Item)
    yield
    get_connection().close()


def run(coro):
    return asyncio.run(coro)


def test_acreate_acount(db):
    async def main():
        await Item.objects.acreate(name="a", n=1)
        await Item.objects.acreate(name="b", n=2)
        return await Item.objects.acount()

    assert run(main()) == 2


def test_abulk_create(db):
    async def main():
        await Item.objects.abulk_create([Item(name=str(i), n=i) for i in range(5)])
        return await Item.objects.acount()

    assert run(main()) == 5


def test_aget(db):
    async def main():
        await Item.objects.acreate(name="x", n=7)
        return (await Item.objects.aget(name="x")).n

    assert run(main()) == 7


def test_alist_and_afirst(db):
    async def main():
        await Item.objects.abulk_create([Item(name="a", n=1), Item(name="b", n=2)])
        rows = await Item.objects.order_by("n").alist()
        first = await Item.objects.order_by("n").afirst()
        return [r.name for r in rows], first.name

    names, first = run(main())
    assert names == ["a", "b"] and first == "a"


def test_async_iteration(db):
    async def main():
        await Item.objects.abulk_create([Item(name="a", n=1), Item(name="b", n=2)])
        out = []
        async for item in Item.objects.order_by("n"):
            out.append(item.name)
        return out

    assert run(main()) == ["a", "b"]


def test_aexists(db):
    async def main():
        return await Item.objects.filter(n=99).aexists()

    assert run(main()) is False


def test_aupdate_adelete(db):
    async def main():
        await Item.objects.abulk_create([Item(name="a", n=1), Item(name="b", n=2)])
        changed = await Item.objects.all().aupdate(n=0)
        deleted = await Item.objects.filter(name="a").adelete()
        return changed, deleted, await Item.objects.acount()

    changed, deleted, remaining = run(main())
    assert changed == 2 and deleted == 1 and remaining == 1


def test_asave_arefresh(db):
    async def main():
        obj = await Item.objects.acreate(name="a", n=1)
        obj.n = 42
        await obj.asave()
        fresh = await Item.objects.aget(pk=obj.pk)
        return fresh.n

    assert run(main()) == 42


def test_aget_or_create(db):
    async def main():
        obj, created = await Item.objects.aget_or_create(name="x", defaults={"n": 5})
        obj2, created2 = await Item.objects.aget_or_create(name="x", defaults={"n": 9})
        return created, created2, obj2.n

    created, created2, n = run(main())
    assert created and not created2 and n == 5


def test_aaggregate(db):
    async def main():
        await Item.objects.abulk_create([Item(name="a", n=1), Item(name="b", n=2)])
        return await Item.objects.aaggregate(c=Count("*"))

    assert run(main()) == {"c": 2}
