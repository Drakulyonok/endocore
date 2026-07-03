"""Generate an OpenAPI 3.0 document from the route registry.

Types are basic (handlers are plain functions, no pydantic): path params are
strings, request bodies are generic objects. Summaries come from handler
docstrings. Enough for a browsable ``/docs`` and client generation.
"""

from __future__ import annotations

import inspect
import sys
from typing import Any

_BODY_METHODS = {"POST", "PUT", "PATCH"}


def _summary(entry) -> str:
    doc = entry.handler.__doc__
    if not doc:  # fall back to the handler file's module docstring
        module = sys.modules.get(getattr(entry.handler, "__module__", ""))
        doc = getattr(module, "__doc__", None) or (inspect.getmodule(entry.handler).__doc__
                                                   if inspect.getmodule(entry.handler) else None)
    doc = (doc or "").strip()
    return doc.splitlines()[0] if doc else f"{entry.spec.method} {entry.spec.url}"


def _body_schema(entry) -> dict:
    """If a handler parameter is a pydantic model, use its JSON schema for the body."""
    from endocore.core.di import is_pydantic_model

    try:
        import typing

        hints = typing.get_type_hints(entry.handler)
    except Exception:  # noqa: BLE001
        hints = {}
    for annotation in hints.values():
        if is_pydantic_model(annotation):
            if hasattr(annotation, "model_json_schema"):
                return annotation.model_json_schema()
            return annotation.schema()  # pydantic v1
    return {"type": "object"}


def generate_openapi(app, *, title: str = "EndoCore API", version: str = "1.0.0") -> dict:
    paths: dict[str, dict] = {}

    for entry in app.registry.entries():
        spec = entry.spec
        if spec.method == "WEBSOCKET":
            continue
        path = spec.url  # already "/v1/user/{id}"
        operation: dict[str, Any] = {
            "summary": _summary(entry),
            "responses": {"200": {"description": "OK"}},
            "tags": [spec.version],
        }
        params = [
            {"name": seg.name, "in": "path", "required": True, "schema": {"type": "string"}}
            for seg in spec.segments if seg.dynamic
        ]
        if params:
            operation["parameters"] = params
        if spec.method in _BODY_METHODS:
            operation["requestBody"] = {
                "content": {"application/json": {"schema": _body_schema(entry)}}
            }
        paths.setdefault(path, {})[spec.method.lower()] = operation

    return {
        "openapi": "3.0.3",
        "info": {"title": title, "version": version},
        "paths": dict(sorted(paths.items())),
    }


SWAGGER_UI_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>API docs</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist/swagger-ui-bundle.js"></script>
  <script>
    window.onload = () => SwaggerUIBundle({ url: '/openapi.json', dom_id: '#swagger-ui' });
  </script>
</body>
</html>
"""
