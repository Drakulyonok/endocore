"""Unified configuration: a typed ``Settings`` object read from the environment.

    from endocore import Settings, env

    class AppSettings(Settings):
        debug: bool = False
        db_url: str = "sqlite://app.db"
        port: int = 8000
        allowed_hosts: list[str] = []

    settings = AppSettings()   # reads DEBUG, DB_URL, PORT, ALLOWED_HOSTS from env

Values come from environment variables named by the UPPERCASED attribute (with
an optional ``_env_prefix``), cast to the annotated type, falling back to the
declared default. ``load_dotenv()`` can seed the environment from a ``.env`` file.
Secret-looking fields are masked in ``repr`` so they don't leak into logs.
"""

from __future__ import annotations

import os
import typing
from pathlib import Path
from typing import Any, Callable

_TRUE = {"1", "true", "yes", "on"}
_SECRET_HINTS = ("secret", "password", "passwd", "token", "key", "dsn")


def as_bool(value: str) -> bool:
    return str(value).strip().lower() in _TRUE


def env(name: str, default: Any = None, cast: Callable[[str], Any] | None = None) -> Any:
    """Read an environment variable, optionally casting it. Missing -> ``default``."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return cast(raw) if cast else raw


def load_dotenv(path: str | Path = ".env", *, override: bool = False) -> None:
    """Load ``KEY=VALUE`` lines from a ``.env`` file into ``os.environ``."""
    file = Path(path)
    if not file.is_file():
        return
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if override or key not in os.environ:
            os.environ[key] = value


def _cast(value: str, annotation: Any) -> Any:
    if annotation is bool:
        return as_bool(value)
    if annotation is int:
        return int(value)
    if annotation is float:
        return float(value)
    if annotation is Path:
        return Path(value)
    origin = typing.get_origin(annotation) or annotation  # handle bare list/tuple/set too
    if origin in (list, tuple, set):
        parts = [part.strip() for part in value.split(",") if part.strip()]
        return list(parts) if origin is list else origin(parts)
    return value


class Settings:
    """Base class for typed, environment-backed configuration."""

    _env_prefix = ""

    def __init__(self, **overrides: Any) -> None:
        hints = typing.get_type_hints(type(self))
        for name, annotation in hints.items():
            if name.startswith("_"):
                continue
            if name in overrides:
                setattr(self, name, overrides[name])
                continue
            env_name = f"{self._env_prefix}{name}".upper()
            if env_name in os.environ:
                setattr(self, name, _cast(os.environ[env_name], annotation))
            else:
                setattr(self, name, getattr(type(self), name, None))

    def _fields(self) -> dict[str, Any]:
        return {n: getattr(self, n) for n in typing.get_type_hints(type(self)) if not n.startswith("_")}

    def __repr__(self) -> str:
        parts = []
        for name, value in self._fields().items():
            if any(hint in name.lower() for hint in _SECRET_HINTS):
                value = "***"
            parts.append(f"{name}={value!r}")
        return f"{type(self).__name__}({', '.join(parts)})"
