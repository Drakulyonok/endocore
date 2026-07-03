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
