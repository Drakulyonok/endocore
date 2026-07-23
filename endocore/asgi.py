"""ASGI entry points for uvicorn.

``endo dev`` runs ``uvicorn "endocore.asgi:create_app" --factory --reload`` and
always sets ``ENDOCORE_DEV`` itself before doing so; the factory reads the
current working directory as the application root, so the reloader picks up
handler changes on the next request.

    uvicorn endocore.asgi:create_app --factory   # serve the app in the CWD

Without ``ENDOCORE_DEV`` set at all — a bare ``uvicorn endocore.asgi:create_app
--factory`` in a raw deployment, not through ``endo dev`` — this defaults to
**off**, matching :class:`~endocore.core.application.Application`'s own
``dev=False`` default: same-origin websocket enforcement, no dev file
watcher, and ``/docs``/``/openapi.json`` require opting in.
"""

from __future__ import annotations

import os

from endocore.core.application import Application


def create_app() -> Application:
    """Build an :class:`Application` rooted at the current working directory.

    Reads env vars set by ``endo dev`` (or the deployment):
    - ``ENDOCORE_DEV``            "1" enables the in-process dev watcher (and
      relaxes the websocket same-origin check); off unless set.
    - ``ENDOCORE_DEFAULT_VERSION`` e.g. "latest" to resolve version-less paths.
    - ``ENDOCORE_OPENAPI``        "1" serves /docs + /openapi.json even with
      ``dev=False`` (they are on in dev, off in production by default).
    """
    dev = os.environ.get("ENDOCORE_DEV", "0") != "0"
    default_version = os.environ.get("ENDOCORE_DEFAULT_VERSION") or None
    openapi_env = os.environ.get("ENDOCORE_OPENAPI")
    openapi = None if openapi_env is None else openapi_env != "0"
    return Application(
        app_dir=os.getcwd(), dev=dev, default_version=default_version, openapi=openapi
    )
