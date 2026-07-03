"""CLI tree operations: create, version create/list (incl. import rewrite)."""

from __future__ import annotations

import argparse

from endocore.cli.commands import create as create_cmd
from endocore.cli.commands import version as version_cmd
from endocore.core.discovery import list_versions


def _seed_v1(root):
    role = root / "Api" / "v1" / "User" / "Role"
    role.mkdir(parents=True)
    (role / "Post.py").write_text(
        "from Api.v1.User.Services.create_role import create_role\n"
        "async def handler(request): ...\n",
        encoding="utf-8",
    )
    services = root / "Api" / "v1" / "User" / "Services"
    services.mkdir(parents=True)
    (services / "create_role.py").write_text("def create_role(p): return p\n", encoding="utf-8")
    # A global service outside Api/ must never be copied.
    (root / "Services").mkdir()
    (root / "Services" / "auth.py").write_text("def auth(): ...\n", encoding="utf-8")


def test_create_endpoint(tmp_path, monkeypatch):
    (tmp_path / "Api" / "v1").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    rc = create_cmd.run(argparse.Namespace(path="user/role", method="post"))
    assert rc == 0
    created = tmp_path / "Api" / "v1" / "User" / "Role" / "Post.py"
    assert created.is_file()
    assert "async def handler" in created.read_text(encoding="utf-8")


def test_create_dynamic_and_versioned(tmp_path, monkeypatch):
    (tmp_path / "Api").mkdir()
    monkeypatch.chdir(tmp_path)

    rc = create_cmd.run(argparse.Namespace(path="v2/user/[id]", method="get"))
    assert rc == 0
    assert (tmp_path / "Api" / "v2" / "User" / "[id]" / "Get.py").is_file()


def test_version_create_copies_and_rewrites_imports(tmp_path, monkeypatch):
    _seed_v1(tmp_path)
    monkeypatch.chdir(tmp_path)

    rc = version_cmd.run(
        argparse.Namespace(version_command="create", number=2, from_version=None, empty=False)
    )
    assert rc == 0

    assert list_versions(tmp_path / "Api") == ["v1", "v2"]
    # Local services were copied...
    assert (tmp_path / "Api" / "v2" / "User" / "Services" / "create_role.py").is_file()
    # ...and the copied handler now imports its OWN version's service.
    post = (tmp_path / "Api" / "v2" / "User" / "Role" / "Post.py").read_text(encoding="utf-8")
    assert "Api.v2.User.Services.create_role" in post
    assert "Api.v1" not in post
    # Global services untouched (still only under root Services/).
    assert not (tmp_path / "Api" / "v2" / "Services").exists()


def test_version_create_refuses_existing(tmp_path, monkeypatch):
    _seed_v1(tmp_path)
    monkeypatch.chdir(tmp_path)
    rc = version_cmd.run(
        argparse.Namespace(version_command="create", number=1, from_version=None, empty=False)
    )
    assert rc == 2  # v1 already exists
