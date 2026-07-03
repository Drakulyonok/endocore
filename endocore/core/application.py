"""The ASGI application: ``async def app(scope, receive, send)``.

Ties the pieces together. At construction it **boots**: scans ``Api/`` (once),
imports handlers (error-resilient), fills the registry and logs a summary
(``loaded N routes, M files with errors``). Per request it builds a
:class:`Request`, runs it through the middleware chain to the endpoint
dispatcher (resolve route -> call handler -> coerce return value), and writes the
:class:`Response`.
"""

from __future__ import annotations

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
from endocore.core.registry import METHOD_NOT_ALLOWED, Registry
from endocore.core.request import Request
from endocore.core.response import Response
from endocore.middleware.logging import logging_middleware


class Application:
    """A booted EndoCore app, callable as an ASGI application."""

    def __init__(self, app_dir: str | Path = ".", *, dev: bool = False) -> None:
        self.app_dir = Path(app_dir).resolve()
        self.api_dir = self.app_dir / "Api"
        self.dev = dev
        self.registry = Registry()
        self.middlewares: list[Middleware] = [logging_middleware]
        self.boot_errors: list[BootError] = []
        self.logger = get_logger()
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

        specs, skipped = scan_routes(self.api_dir)
        self.boot_errors = []

        for spec in specs:
            try:
                entry = load_handler(spec, self.app_dir)
            except BaseException as exc:  # noqa: BLE001 - one file must not kill boot
                self.boot_errors.append(BootError(spec.file, exc, traceback.format_exc()))
                continue
            self.registry.add(entry)

        # Logging is always outermost (it times auth and everything else);
        # user middleware from Middleware/ sits inside it, then the dispatcher.
        user_middlewares = self._load_user_middlewares()
        self.middlewares = [logging_middleware, *user_middlewares]

        # Build the request pipeline once; middlewares are fixed after boot.
        self._pipeline = build_chain(self.middlewares, self._dispatch)

        self._log_boot_summary(skipped, len(user_middlewares))

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

    @staticmethod
    def _coerce(result: Any) -> Response:
        """Turn a handler's return value into a Response."""
        if isinstance(result, Response):
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
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
