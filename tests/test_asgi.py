"""``endocore.asgi:create_app`` — the factory a bare ``uvicorn ... --factory``
deployment uses directly, with no ``endo dev`` in between to set env vars."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from endocore.asgi import create_app


@pytest.fixture()
def app_dir(tmp_path, monkeypatch):
    (tmp_path / "Api").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in ("ENDOCORE_DEV", "ENDOCORE_DEFAULT_VERSION", "ENDOCORE_OPENAPI"):
        monkeypatch.delenv(key, raising=False)


def test_dev_defaults_to_off_without_the_env_var(app_dir):
    """A bare `uvicorn endocore.asgi:create_app --factory` in production, with
    no ENDOCORE_DEV set at all, must not silently boot in dev mode — that
    would relax the websocket same-origin check and expose /docs by default."""
    app = create_app()
    assert app.dev is False


def test_dev_enabled_when_env_var_is_one(app_dir, monkeypatch):
    monkeypatch.setenv("ENDOCORE_DEV", "1")
    app = create_app()
    assert app.dev is True


def test_dev_explicitly_disabled(app_dir, monkeypatch):
    monkeypatch.setenv("ENDOCORE_DEV", "0")
    app = create_app()
    assert app.dev is False


def test_openapi_off_by_default_matching_dev_off(app_dir):
    app = create_app()
    assert app.openapi is False


def test_openapi_can_be_forced_on_in_production(app_dir, monkeypatch):
    monkeypatch.setenv("ENDOCORE_DEV", "0")
    monkeypatch.setenv("ENDOCORE_OPENAPI", "1")
    app = create_app()
    assert app.dev is False
    assert app.openapi is True


def test_default_version_env_var(app_dir, monkeypatch):
    monkeypatch.setenv("ENDOCORE_DEFAULT_VERSION", "latest")
    app = create_app()
    assert app.default_version == "latest"


def test_app_dir_is_the_current_working_directory(app_dir):
    app = create_app()
    assert app.app_dir == Path(app_dir).resolve()
