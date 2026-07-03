"""Dependency injection for handlers.

Handlers stay plain functions; extra parameters are resolved by name/type:

    from endocore import Request, Response, Depends

    async def db():                       # a dependency (may be async)
        return get_pool()

    async def current_user(request: Request, pool = Depends(db)):
        return await pool.user_from(request.headers.get("authorization"))

    async def handler(request: Request, user = Depends(current_user)):
        return Response.json({"user": user})

Resolution rules for each parameter, in order:
1. ``request`` (by name or ``Request`` annotation) -> the Request.
2. default is ``Depends(fn)`` -> ``fn`` is resolved (recursively) and called.
3. name matches a captured path param (``[id]``) -> that value.
4. an app-level provider registered for the annotation/type or name.
5. the parameter's own default, if any.

Dependencies are cached per-request, so a dependency used twice runs once.
App-level providers may be singletons (built once, reused).
"""

from __future__ import annotations

import inspect
import typing
from typing import Any, Callable

from endocore.core.exceptions import EndoCoreError

_EMPTY = inspect.Parameter.empty
_sig_cache: dict[Callable, inspect.Signature] = {}
_hint_cache: dict[Callable, dict] = {}


class DIError(EndoCoreError):
    """A handler/dependency parameter could not be resolved."""


class Depends:
    """Marker used as a parameter default to request injection of ``dependency``."""

    __slots__ = ("dependency",)

    def __init__(self, dependency: Callable) -> None:
        self.dependency = dependency

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        name = getattr(self.dependency, "__name__", self.dependency)
        return f"Depends({name})"


def _signature(func: Callable) -> inspect.Signature:
    sig = _sig_cache.get(func)
    if sig is None:
        sig = inspect.signature(func)
        _sig_cache[func] = sig
    return sig


def _hints(func: Callable) -> dict:
    """Resolved type hints, so string annotations (``from __future__ import
    annotations``) still map to real types for type-based injection."""
    hints = _hint_cache.get(func)
    if hints is None:
        try:
            hints = typing.get_type_hints(func)
        except Exception:  # noqa: BLE001 - unresolvable annotations fall back to raw
            hints = {}
        _hint_cache[func] = hints
    return hints


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def solve(func: Callable, request, app, cache: dict | None = None, *, websocket=None) -> dict:
    """Build the keyword arguments to call ``func`` with, resolving dependencies."""
    if cache is None:
        cache = {}
    kwargs: dict[str, Any] = {}
    hints = _hints(func)
    for name, param in _signature(func).parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        annotation = hints.get(name, param.annotation)
        kwargs[name] = await _resolve(func, name, param, annotation, request, app, cache, websocket)
    return kwargs


async def _resolve(func, name, param, annotation, request, app, cache, websocket=None) -> Any:
    from endocore.core.request import Request
    from endocore.core.websocket import WebSocket

    default = param.default

    if isinstance(default, Depends):
        return await _resolve_depends(default, request, app, cache, websocket)

    if name == "request" or annotation is Request:
        return request

    if name == "websocket" or annotation is WebSocket:
        return websocket

    scope_obj = request if request is not None else websocket
    if scope_obj is not None and name in getattr(scope_obj, "path_params", {}):
        return scope_obj.path_params[name]

    if app is not None:
        provider = app.get_provider(annotation, name)
        if provider is not None:
            return await _resolve_provider(provider, request, app, cache, websocket)

    if request is not None and is_pydantic_model(annotation):
        return await _validate_body(annotation, request)

    if default is not _EMPTY:
        return default

    raise DIError(f"cannot resolve parameter {name!r} of {getattr(func, '__name__', func)!r}")


def is_pydantic_model(annotation) -> bool:
    """Whether ``annotation`` is a pydantic ``BaseModel`` subclass (v1 or v2)."""
    if not isinstance(annotation, type):
        return False
    try:
        from pydantic import BaseModel
    except ImportError:
        return False
    return issubclass(annotation, BaseModel)


async def _validate_body(model, request):
    """Parse and validate the JSON body into a pydantic model (422 on error)."""
    from pydantic import ValidationError

    from endocore.core.exceptions import UnprocessableEntity

    data = await request.json()
    try:
        if hasattr(model, "model_validate"):  # pydantic v2
            return model.model_validate(data or {})
        return model.parse_obj(data or {})    # pydantic v1
    except ValidationError as exc:
        errors = [
            {"field": ".".join(str(p) for p in err.get("loc", ())), "message": err.get("msg", "invalid")}
            for err in exc.errors()
        ]
        raise UnprocessableEntity(errors) from None


async def _resolve_depends(dep: Depends, request, app, cache, websocket=None) -> Any:
    key = dep.dependency
    if key in cache:
        return cache[key]
    sub = await solve(dep.dependency, request, app, cache, websocket=websocket)
    value = await _maybe_await(dep.dependency(**sub))
    cache[key] = value
    return value


async def _resolve_provider(provider, request, app, cache, websocket=None) -> Any:
    factory, singleton = provider
    if singleton and factory in app._singletons:
        return app._singletons[factory]
    sub = await solve(factory, request, app, cache, websocket=websocket)
    value = await _maybe_await(factory(**sub))
    if singleton:
        app._singletons[factory] = value
    return value


class ProviderRegistry:
    """App-level providers, resolvable by annotation (type) or parameter name."""

    def __init__(self) -> None:
        self.by_type: dict[type, tuple[Callable, bool]] = {}
        self.by_name: dict[str, tuple[Callable, bool]] = {}

    def provide(self, key, factory: Callable, *, singleton: bool = True) -> None:
        entry = (factory, singleton)
        if isinstance(key, type):
            self.by_type[key] = entry
        else:
            self.by_name[str(key)] = entry

    def get(self, annotation, name) -> tuple[Callable, bool] | None:
        if annotation is not _EMPTY and annotation in self.by_type:
            return self.by_type[annotation]
        return self.by_name.get(name)
