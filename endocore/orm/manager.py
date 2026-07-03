"""Manager — the ``Model.objects`` entry point that hands out QuerySets."""

from __future__ import annotations

from typing import Any

from endocore.orm.query import QuerySet


def get_queryset(model) -> QuerySet:
    return QuerySet(model)


class Manager:
    """Thin facade delegating to a fresh QuerySet for each call."""

    def contribute_to_class(self, model) -> None:
        self.model = model

    def get_queryset(self) -> QuerySet:
        return QuerySet(self.model)

    # Delegate the common entry points so `Model.objects.filter(...)` reads well.
    def all(self) -> QuerySet:
        return self.get_queryset()

    def none(self) -> QuerySet:
        return self.get_queryset().none()

    def in_bulk(self, ids) -> dict:
        return self.get_queryset().in_bulk(ids)

    def filter(self, *args, **kwargs) -> QuerySet:
        return self.get_queryset().filter(*args, **kwargs)

    def exclude(self, *args, **kwargs) -> QuerySet:
        return self.get_queryset().exclude(*args, **kwargs)

    def order_by(self, *fields) -> QuerySet:
        return self.get_queryset().order_by(*fields)

    def distinct(self) -> QuerySet:
        return self.get_queryset().distinct()

    def select_related(self, *paths) -> QuerySet:
        return self.get_queryset().select_related(*paths)

    def prefetch_related(self, *names) -> QuerySet:
        return self.get_queryset().prefetch_related(*names)

    def only(self, *fields) -> QuerySet:
        return self.get_queryset().only(*fields)

    def defer(self, *fields) -> QuerySet:
        return self.get_queryset().defer(*fields)

    def annotate(self, **annotations) -> QuerySet:
        return self.get_queryset().annotate(**annotations)

    def bulk_update(self, objects: list, fields: list) -> int:
        return self.get_queryset().bulk_update(objects, fields)

    # -- async API --------------------------------------------------------

    async def aget(self, *args, **kwargs):
        return await self.get_queryset().aget(*args, **kwargs)

    async def acreate(self, **kwargs):
        return await self.get_queryset().acreate(**kwargs)

    async def acount(self) -> int:
        return await self.get_queryset().acount()

    async def aexists(self) -> bool:
        return await self.get_queryset().aexists()

    async def afirst(self):
        return await self.get_queryset().afirst()

    async def alast(self):
        return await self.get_queryset().alast()

    async def alist(self) -> list:
        return await self.get_queryset().alist()

    async def aget_or_create(self, defaults: dict | None = None, **kwargs):
        return await self.get_queryset().aget_or_create(defaults, **kwargs)

    async def aupdate_or_create(self, defaults: dict | None = None, **kwargs):
        return await self.get_queryset().aupdate_or_create(defaults, **kwargs)

    async def abulk_create(self, objects: list) -> list:
        return await self.get_queryset().abulk_create(objects)

    async def abulk_update(self, objects: list, fields: list) -> int:
        return await self.get_queryset().abulk_update(objects, fields)

    async def aaggregate(self, **kwargs) -> dict:
        return await self.get_queryset().aaggregate(**kwargs)

    def values(self, *fields) -> QuerySet:
        return self.get_queryset().values(*fields)

    def values_list(self, *fields, flat: bool = False) -> QuerySet:
        return self.get_queryset().values_list(*fields, flat=flat)

    def get(self, *args, **kwargs):
        return self.get_queryset().get(*args, **kwargs)

    def first(self):
        return self.get_queryset().first()

    def last(self):
        return self.get_queryset().last()

    def count(self) -> int:
        return self.get_queryset().count()

    def exists(self) -> bool:
        return self.get_queryset().exists()

    def create(self, **kwargs: Any):
        return self.get_queryset().create(**kwargs)

    def bulk_create(self, objects: list) -> list:
        return self.get_queryset().bulk_create(objects)

    def aggregate(self, **kwargs):
        return self.get_queryset().aggregate(**kwargs)

    def earliest(self, field: str):
        return self.get_queryset().earliest(field)

    def latest(self, field: str):
        return self.get_queryset().latest(field)

    def get_or_create(self, defaults: dict | None = None, **kwargs):
        return self.get_queryset().get_or_create(defaults, **kwargs)

    def update_or_create(self, defaults: dict | None = None, **kwargs):
        return self.get_queryset().update_or_create(defaults, **kwargs)
