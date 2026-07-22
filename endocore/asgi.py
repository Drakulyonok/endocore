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

    Reads env vars set by ``end dev`` (or the deployment):
    - ``ENDOCORE_DEV``            "0" disables the in-process dev watcher.
    - ``ENDOCORE_DEFAULT_VERSION`` e.g. "latest" to resolve version-less paths.
    - ``ENDOCORE_OPENAPI``        "1" serves /docs + /openapi.json even with
      ``dev=False`` (they are on in dev, off in production by default).
    """
    dev = os.environ.get("ENDOCORE_DEV", "1") != "0"
    default_version = os.environ.get("ENDOCORE_DEFAULT_VERSION") or None
    openapi_env = os.environ.get("ENDOCORE_OPENAPI")
    openapi = None if openapi_env is None else openapi_env != "0"
    return Application(
        app_dir=os.getcwd(), dev=dev, default_version=default_version, openapi=openapi
    )
