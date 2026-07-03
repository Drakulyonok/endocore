"""Settings / env / dotenv coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from endocore.core.config import Settings, as_bool, env, load_dotenv


@pytest.mark.parametrize("value,expected", [
    ("1", True), ("true", True), ("True", True), ("yes", True), ("on", True), ("YES", True),
    ("0", False), ("false", False), ("no", False), ("off", False), ("", False), ("nope", False),
])
def test_as_bool(value, expected):
    assert as_bool(value) is expected


@pytest.mark.parametrize("present,default,expected", [
    (True, None, "value"), (False, None, None), (False, "d", "d"), (False, 42, 42),
])
def test_env(monkeypatch, present, default, expected):
    if present:
        monkeypatch.setenv("ENDO_TEST_X", "value")
    else:
        monkeypatch.delenv("ENDO_TEST_X", raising=False)
    assert env("ENDO_TEST_X", default) == expected


@pytest.mark.parametrize("raw,cast,expected", [
    ("42", int, 42), ("3.14", float, 3.14), ("1", as_bool, True), ("a,b", lambda v: v.split(","), ["a", "b"]),
])
def test_env_cast(monkeypatch, raw, cast, expected):
    monkeypatch.setenv("ENDO_TEST_C", raw)
    assert env("ENDO_TEST_C", cast=cast) == expected


class Conf(Settings):
    debug: bool = False
    port: int = 8000
    ratio: float = 1.0
    name: str = "app"
    hosts: list = []
    data_dir: Path = Path(".")


@pytest.mark.parametrize("field,env_name,raw,expected", [
    ("debug", "DEBUG", "true", True),
    ("debug", "DEBUG", "0", False),
    ("port", "PORT", "9999", 9999),
    ("ratio", "RATIO", "2.5", 2.5),
    ("name", "NAME", "prod", "prod"),
    ("hosts", "HOSTS", "a,b,c", ["a", "b", "c"]),
    ("data_dir", "DATA_DIR", "/var/data", Path("/var/data")),
])
def test_settings_from_env(monkeypatch, field, env_name, raw, expected):
    monkeypatch.setenv(env_name, raw)
    assert getattr(Conf(), field) == expected


def test_settings_defaults(monkeypatch):
    for name in ("DEBUG", "PORT", "RATIO", "NAME", "HOSTS", "DATA_DIR"):
        monkeypatch.delenv(name, raising=False)
    conf = Conf()
    assert conf.debug is False and conf.port == 8000 and conf.name == "app" and conf.hosts == []


def test_settings_overrides():
    conf = Conf(port=1234, name="x")
    assert conf.port == 1234 and conf.name == "x"


class Secretive(Settings):
    api_key: str = "sk-123"
    password: str = "hunter2"
    name: str = "public"


def test_settings_repr_masks_secrets():
    text = repr(Secretive())
    assert "sk-123" not in text and "hunter2" not in text
    assert "public" in text and "***" in text


@pytest.mark.parametrize("content,key,expected", [
    ("A=1\nB=two", "A", "1"),
    ("A=1\nB=two", "B", "two"),
    ('QUOTED="hello world"', "QUOTED", "hello world"),
    ("# comment\nC=3", "C", "3"),
    ("EMPTY=", "EMPTY", ""),
])
def test_load_dotenv(tmp_path, monkeypatch, content, key, expected):
    monkeypatch.delenv(key, raising=False)
    envfile = tmp_path / ".env"
    envfile.write_text(content, encoding="utf-8")
    load_dotenv(envfile)
    assert env(key) == expected


def test_load_dotenv_no_override(tmp_path, monkeypatch):
    monkeypatch.setenv("EXIST", "original")
    (tmp_path / ".env").write_text("EXIST=new", encoding="utf-8")
    load_dotenv(tmp_path / ".env")
    assert env("EXIST") == "original"
