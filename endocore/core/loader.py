"""Dynamic import of handler files — the "autoscan" (``importlib``).

Each endpoint file must define a ``handler`` callable (sync or async):

    async def handler(request: Request) -> Response: ...

Optionally it may define ``init()``, called once at boot for setup (detected via
``inspect``).

Robustness (TZ §4.1): every import is wrapped in try/except by the caller. One
broken file must not bring down the whole boot — failures are collected as
:class:`BootError` and reported in the boot summary.
"""

from __future__ import annotations

import importlib.util
import inspect
import re
import sys
from pathlib import Path

from endocore.core.discovery import RouteSpec
from endocore.core.exceptions import HandlerContractError
from endocore.core.registry import HandlerEntry

_UNSAFE = re.compile(r"[^0-9a-zA-Z_]")


def module_name_for(file: Path, app_dir: Path) -> str:
    """Build a stable, collision-free module name from the file's tree path.

    ``Api/v1/User/[id]/Get.py`` -> ``endocore_app.Api.v1.User._id_.Get``. The
    name only keys ``sys.modules``; it is never imported by name, so sanitizing
    ``[id]`` -> ``_id_`` is safe.
    """
    rel = file.relative_to(app_dir).with_suffix("")
    parts = [_UNSAFE.sub("_", part) for part in rel.parts]
    return "endocore_app." + ".".join(parts)


def load_handler(spec: RouteSpec, app_dir: Path) -> HandlerEntry:
    """Import ``spec.file`` and extract its ``handler`` (running ``init()`` once).

    Raises :class:`HandlerContractError` if no ``handler`` is defined, or
    propagates the import error to the caller, which decides how to record it.
    """
    modname = module_name_for(spec.file, app_dir)
    module_spec = importlib.util.spec_from_file_location(modname, spec.file)
    if module_spec is None or module_spec.loader is None:
        raise HandlerContractError(f"cannot load {spec.file}")

    module = importlib.util.module_from_spec(module_spec)
    sys.modules[modname] = module
    try:
        module_spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(modname, None)  # don't leave a half-initialized module
        raise

    handler = getattr(module, "handler", None)
    if not callable(handler):
        raise HandlerContractError(
            f"{spec.file} defines no 'handler' callable (endpoint contract)"
        )

    init = getattr(module, "init", None)
    if callable(init):
        init()

    return HandlerEntry(
        spec=spec,
        handler=handler,
        is_async=inspect.iscoroutinefunction(handler),
    )
