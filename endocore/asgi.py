"""ASGI entry points for uvicorn.

``end dev`` runs ``uvicorn "endocore.asgi:create_app" --factory --reload``; the
factory reads the current working directory as the application root, so the
reloader picks up handler changes on the next request.

    uvicorn endocore.asgi:create_app --factory   # serve the app in the CWD
"""

from __future__ import annotations

import os

from endocore.core.application import Application


def create_app() -> Application:
    """Build an :class:`Application` rooted at the current working directory.

    Reads two env vars set by ``end dev``:
    - ``ENDOCORE_DEV``            "0" disables the in-process dev watcher.
    - ``ENDOCORE_DEFAULT_VERSION`` e.g. "latest" to resolve version-less paths.
    """
    dev = os.environ.get("ENDOCORE_DEV", "1") != "0"
    default_version = os.environ.get("ENDOCORE_DEFAULT_VERSION") or None
    return Application(app_dir=os.getcwd(), dev=dev, default_version=default_version)
