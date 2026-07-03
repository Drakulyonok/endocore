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
    """Build an :class:`Application` rooted at the current working directory."""
    return Application(app_dir=os.getcwd(), dev=True)
