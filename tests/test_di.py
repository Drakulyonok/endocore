"""Dependency injection resolution coverage."""

from __future__ import annotations

import asyncio

import pytest

from endocore.core.di import Depends, DIError, ProviderRegistry, solve


class _App:
    """Minimal app stub exposing the provider protocol used by solve()."""

    def __init__(self):
        self.providers = ProviderRegistry()
        self._singletons = {}

    def get_provider(self, annotation, name):
        return self.providers.get(annotation, name)


class Service:
    pass


def _resolve(func, request=None, app=None):
    return asyncio.run(solve(func, request, app))


def test_request_by_name():
    async def h(request):
        return request

    kwargs = _resolve(h, request="REQ")
    assert kwargs == {"request": "REQ"}


def test_default_used():
    async def h(x=5):
        return x

    assert _resolve(h) == {"x": 5}


def test_missing_raises():
    async def h(x):
        return x

    with pytest.raises(DIError):
        _resolve(h)


@pytest.mark.parametrize("value", [1, "a", {"k": "v"}, [1, 2], None, True])
def test_depends_simple(value):
    def dep():
        return value

    async def h(v=Depends(dep)):
        return v

    assert _resolve(h)["v"] == value


def test_depends_async():
    async def dep():
        return "async-value"

    async def h(v=Depends(dep)):
        return v

    assert _resolve(h)["v"] == "async-value"


def test_nested_depends():
    def a():
        return 1

    def b(x=Depends(a)):
        return x + 1

    async def h(y=Depends(b)):
        return y

    assert _resolve(h)["y"] == 2


def test_depends_cached_per_request():
    calls = {"n": 0}

    def dep():
        calls["n"] += 1
        return calls["n"]

    def one(a=Depends(dep)):
        return a

    def two(a=Depends(dep)):
        return a

    async def h(x=Depends(one), y=Depends(two)):
        return x, y

    kwargs = _resolve(h)
    assert kwargs["x"] == kwargs["y"]  # dep ran once, shared
    assert calls["n"] == 1


def test_path_param_injection():
    async def h(id):
        return id

    class Req:
        path_params = {"id": "42"}

    assert _resolve(h, request=Req())["id"] == "42"


def test_provider_by_name():
    app = _App()
    app.providers.provide("db", lambda: "POOL")

    async def h(db):
        return db

    assert asyncio.run(solve(h, None, app))["db"] == "POOL"


def test_provider_by_type():
    svc = Service()
    app = _App()
    app.providers.provide(Service, lambda: svc)

    async def h(s: Service):
        return s

    assert asyncio.run(solve(h, None, app))["s"] is svc


def test_provider_singleton_cached():
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return object()

    app = _App()
    app.providers.provide("thing", factory, singleton=True)

    async def h(thing):
        return thing

    a = asyncio.run(solve(h, None, app))["thing"]
    b = asyncio.run(solve(h, None, app))["thing"]
    assert a is b and calls["n"] == 1


def test_provider_non_singleton():
    app = _App()
    app.providers.provide("thing", lambda: object(), singleton=False)

    async def h(thing):
        return thing

    a = asyncio.run(solve(h, None, app))["thing"]
    b = asyncio.run(solve(h, None, app))["thing"]
    assert a is not b
