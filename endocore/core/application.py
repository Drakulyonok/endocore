"""The ASGI application: ``async def app(scope, receive, send)``.

Ties the pieces together. At construction it **boots**: scans ``Api/`` (once),
imports handlers (error-resilient), fills the registry and logs a summary
(``loaded N routes, M files with errors``). Per request it builds a
:class:`Request`, runs it through the middleware chain to the endpoint
dispatcher (resolve route -> call handler -> coerce return value), and writes the
:class:`Response`.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
import traceback
from pathlib import Path
from typing import Any

from endocore.core.discovery import scan_routes
from endocore.core.exceptions import BootError, HTTPError
from endocore.core.loader import load_handler
from endocore.core.logging import get_logger
from endocore.core.middleware import Middleware, build_chain
from endocore.core.registry import METHOD_NOT_ALLOWED, NOT_FOUND, Registry
from endocore.core.request import Request
from endocore.core.response import Response, StreamingResponse
from endocore.core.router import is_version, split_path
from endocore.middleware.logging import logging_middleware


class Application:
    """A booted EndoCore app, callable as an ASGI application."""

    def __init__(
        self,
        app_dir: str | Path = ".",
        *,
        dev: bool = False,
        default_version: str | None = None,
    ) -> None:
        self.app_dir = Path(app_dir).resolve()
        self.api_dir = self.app_dir / "Api"
        self.dev = dev
        #: ``"latest"`` resolves a version-less path to the newest version (logged);
        #: ``None`` keeps the strict 404 behaviour.
        self.default_version = default_version
        self.registry = Registry()
        self.middlewares: list[Middleware] = [logging_middleware]
        self.boot_errors: list[BootError] = []
        self.logger = get_logger()
        self._watch_task: asyncio.Task | None = None
        self.boot()

    # -- boot -------------------------------------------------------------

    def boot(self) -> None:
        """Scan, import, register, and log the summary. Never raises on a single
        broken handler file — those are collected into ``boot_errors``."""
        # Make the app importable so handlers can `from Services... import ...`
        # and `from Api.vN... import ...` (namespace packages, no __init__ needed).
        app_path = str(self.app_dir)
        if app_path not in sys.path:
            sys.path.insert(0, app_path)

        skipped = self._load_registry()

        # Logging is always outermost (it times auth and everything else);
        # user middleware from Middleware/ sits inside it, then the dispatcher.
        user_middlewares = self._load_user_middlewares()
        self.middlewares = [logging_middleware, *user_middlewares]

        # Build the request pipeline once; middlewares are fixed after boot.
        # ``_dispatch`` reads ``self.registry`` on every call, so reload() only
        # needs to swap the registry, not rebuild the pipeline.
        self._pipeline = build_chain(self.middlewares, self._dispatch)

        self._log_boot_summary(skipped, len(user_middlewares))

    def _load_registry(self):
        """(Re)scan Api/ and (re)import handlers into a fresh registry."""
        self.registry = Registry()
        self.boot_errors = []
        specs, skipped = scan_routes(self.api_dir)
        for spec in specs:
            try:
                entry = load_handler(spec, self.app_dir)
            except BaseException as exc:  # noqa: BLE001 - one file must not kill boot
                self.boot_errors.append(BootError(spec.file, exc, traceback.format_exc()))
                continue
            self.registry.add(entry)
        return skipped

    def reload(self) -> None:
        """Rebuild the route tree in-process (used by the dev watcher)."""
        self._load_registry()
        self.logger.info(
            "reloaded: %d routes, %d files with errors", len(self.registry), len(self.boot_errors)
        )

    def _load_user_middlewares(self) -> list[Middleware]:
        """Load the ordered ``middlewares`` list from the app's ``Middleware`` package.

        Convention: ``Middleware/__init__.py`` may expose ``middlewares`` — an
        ordered list of ``async (request, call_next) -> Response`` callables. The
        first runs outermost (just inside logging). Absent package or attribute
        means no user middleware; a broken one is recorded, not fatal.
        """
        if not (self.app_dir / "Middleware" / "__init__.py").is_file():
            return []
        try:
            # Drop a cached copy so `end dev` reload picks up edits.
            sys.modules.pop("Middleware", None)
            module = importlib.import_module("Middleware")
            middlewares = list(getattr(module, "middlewares", []))
        except BaseException as exc:  # noqa: BLE001 - never crash boot on user code
            self.boot_errors.append(
                BootError(self.app_dir / "Middleware", exc, traceback.format_exc())
            )
            return []
        return [mw for mw in middlewares if callable(mw)]

    def _log_boot_summary(self, skipped, user_middleware_count: int) -> None:
        self.logger.info(
            "EndoCore booted: loaded %d routes, %d middleware, %d files with errors (app_dir=%s)",
            len(self.registry),
            user_middleware_count,
            len(self.boot_errors),
            self.app_dir,
        )
        for err in self.boot_errors:
            self.logger.error("failed to load %s: %r\n%s", err.path, err.error, err.tb.rstrip())

    # -- request dispatch -------------------------------------------------

    async def _dispatch(self, request: Request) -> Response:
        """Terminal layer of the chain: resolve the route and call the handler."""
        resolution = self.registry.resolve(request.method, request.path)

        # Opt-in: a version-less request may fall back to the newest version.
        if resolution.match is None and resolution.status == NOT_FOUND and self.default_version:
            resolution = self._resolve_default_version(request) or resolution

        if resolution.match is None:
            if resolution.status == METHOD_NOT_ALLOWED:
                return Response.json(
                    {"error": "Method Not Allowed"},
                    status=405,
                    headers={"Allow": ", ".join(resolution.allowed)},
                )
            return Response.json({"error": "Not Found"}, status=404)

        request.path_params = resolution.match.params
        entry = resolution.match.entry
        try:
            result = entry.handler(request)
            if entry.is_async:
                result = await result
        except HTTPError as exc:
            # Handlers may raise to short-circuit with a status (e.g. 404, 422).
            return Response.json({"error": exc.detail or "error"}, status=exc.status)
        return self._coerce(result)

    def _resolve_default_version(self, request: Request):
        """When ``default_version == "latest"`` and the path has no version prefix,
        retry against the newest version and log which one served the request."""
        if self.default_version != "latest":
            return None
        segments = split_path(request.path)
        if segments and is_version(segments[0]):
            return None  # an explicit (but unknown) version stays a 404
        latest = self.registry.latest_version()
        if latest is None:
            return None
        alt = self.registry.resolve(request.method, f"/{latest}{request.path}")
        if alt.match is not None:
            self.logger.info(
                "no version in %s %s -> served %s", request.method, request.path, latest
            )
            return alt
        return None

    @staticmethod
    def _coerce(result: Any):
        """Turn a handler's return value into a Response (or pass a streaming one)."""
        if isinstance(result, (Response, StreamingResponse)):
            return result
        if result is None:
            return Response(None, status=204)
        if isinstance(result, tuple):
            # (content, status) or (content, status, headers)
            content, status, *rest = result
            headers = rest[0] if rest else None
            return Response(content, status=status, headers=headers)
        if isinstance(result, str):
            return Response.text(result)
        return Response.json(result)

    # -- ASGI -------------------------------------------------------------

    async def __call__(self, scope: dict, receive, send) -> None:
        """ASGI entry point. Handles ``lifespan`` and ``http`` scopes."""
        scope_type = scope["type"]

        if scope_type == "lifespan":
            await self._lifespan(receive, send)
            return

        if scope_type != "http":
            return  # websockets etc. are out of MVP scope

        request = Request(scope, receive)
        response = await self._pipeline(request)
        await response(send)

    async def _lifespan(self, receive, send) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                self._start_watcher()
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                self._stop_watcher()
                await send({"type": "lifespan.shutdown.complete"})
                return

    # -- dev watcher (in-process route reload) ----------------------------

    def _start_watcher(self) -> None:
        """In dev, watch the app tree and rebuild the route registry in-process
        on change (TZ §4.1) — no process restart. Needs ``watchfiles``."""
        if not self.dev or self._watch_task is not None:
            return
        try:
            import watchfiles  # noqa: F401
        except ImportError:
            self.logger.info("dev watcher disabled (install 'watchfiles' for auto-reload)")
            return
        self._watch_task = asyncio.ensure_future(self._watch())

    def _stop_watcher(self) -> None:
        if self._watch_task is not None:
            self._watch_task.cancel()
            self._watch_task = None

    async def _watch(self) -> None:
        from watchfiles import awatch

        self.logger.info("dev watcher on: %s", self.api_dir)
        try:
            async for _changes in awatch(self.app_dir):
                try:
                    self.reload()
                except Exception:  # noqa: BLE001 - a bad edit must not kill the watcher
                    self.logger.error("reload failed:\n%s", traceback.format_exc().rstrip())
        except asyncio.CancelledError:
            pass
