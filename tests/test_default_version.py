"""Opt-in default-version resolution (version-less path -> newest version)."""

from __future__ import annotations

from endocore.core.application import Application

from tests.conftest import EXAMPLE_DIR, call


def test_version_less_path_served_by_latest():
    app = Application(app_dir=EXAMPLE_DIR, default_version="latest")
    status, _, _ = call(app, "GET", "/user/role")  # no version prefix
    assert status == 200


def test_without_default_stays_404():
    app = Application(app_dir=EXAMPLE_DIR)  # default_version=None (strict)
    status, _, _ = call(app, "GET", "/user/role")
    assert status == 404


def test_unknown_explicit_version_still_404():
    app = Application(app_dir=EXAMPLE_DIR, default_version="latest")
    status, _, _ = call(app, "GET", "/v9/user/role")  # explicit but unknown
    assert status == 404
