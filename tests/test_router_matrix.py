"""Router/registry resolution matrix."""

from __future__ import annotations

from pathlib import Path

import pytest

from endocore.core.discovery import RouteSpec, Segment
from endocore.core.registry import FOUND, METHOD_NOT_ALLOWED, NOT_FOUND, HandlerEntry, Registry
from endocore.core.router import is_version, split_path


def _entry(version, method, *segments):
    segs = tuple(Segment.parse(s) for s in segments)
    spec = RouteSpec(version=version, method=method, segments=segs, file=Path("x"))
    return HandlerEntry(spec=spec, handler=lambda r: None, is_async=False)


def _registry():
    reg = Registry()
    reg.add(_entry("v1", "GET", "User", "Role"))
    reg.add(_entry("v1", "POST", "User", "Role"))
    reg.add(_entry("v1", "GET", "User", "[id]"))
    reg.add(_entry("v1", "DELETE", "User", "[id]"))
    reg.add(_entry("v2", "GET", "User", "Role"))
    reg.add(_entry("v2", "GET", "Item", "[id]", "Detail"))
    return reg


RESOLVE_CASES = [
    ("GET", "/v1/user/role", FOUND, {}),
    ("POST", "/v1/user/role", FOUND, {}),
    ("GET", "/v1/user/42", FOUND, {"id": "42"}),
    ("DELETE", "/v1/user/7", FOUND, {"id": "7"}),
    ("GET", "/v2/user/role", FOUND, {}),
    ("GET", "/v2/item/99/detail", FOUND, {"id": "99"}),
    ("GET", "/user/role", NOT_FOUND, None),
    ("GET", "/v9/user/role", NOT_FOUND, None),
    ("GET", "/v1/nope", NOT_FOUND, None),
    ("PATCH", "/v1/user/role", METHOD_NOT_ALLOWED, None),
    ("POST", "/v2/user/role", METHOD_NOT_ALLOWED, None),
    ("GET", "/v2/user/42", NOT_FOUND, None),
]


@pytest.mark.parametrize("method,path,status,params", RESOLVE_CASES)
def test_resolve(method, path, status, params):
    res = _registry().resolve(method, path)
    assert res.status == status
    if params is not None:
        assert res.match.params == params
    else:
        assert res.match is None


@pytest.mark.parametrize("path,expected", [
    ("/v1/user/role", ["v1", "user", "role"]),
    ("/", []),
    ("//a//b//", ["a", "b"]),
    ("/v2/user/42", ["v2", "user", "42"]),
    ("/a%20b", ["a b"]),
])
def test_split_path(path, expected):
    assert split_path(path) == expected


@pytest.mark.parametrize("seg,ok", [
    ("v1", True), ("v2", True), ("v10", True), ("v0", True),
    ("v", False), ("version1", False), ("1v", False), ("user", False), ("", False),
])
def test_is_version(seg, ok):
    assert is_version(seg) is bool(ok)


@pytest.mark.parametrize("folder,name,dynamic", [
    ("User", "user", False),
    ("Role", "role", False),
    ("[id]", "id", True),
    ("[slug]", "slug", True),
    ("ITEM", "item", False),
])
def test_segment_parse(folder, name, dynamic):
    seg = Segment.parse(folder)
    assert seg.name == name and seg.dynamic is dynamic


def test_static_beats_dynamic():
    reg = Registry()
    reg.add(_entry("v1", "GET", "User", "[id]"))
    reg.add(_entry("v1", "GET", "User", "Me"))
    assert reg.resolve("GET", "/v1/user/me").match.params == {}
    assert reg.resolve("GET", "/v1/user/123").match.params == {"id": "123"}


def test_latest_version():
    reg = _registry()
    assert reg.latest_version() == "v2"
    assert Registry().latest_version() is None


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
def test_method_allowed_header(method):
    reg = Registry()
    reg.add(_entry("v1", "GET", "X"))
    reg.add(_entry("v1", "POST", "X"))
    res = reg.resolve(method, "/v1/x")
    if method in ("GET", "POST"):
        assert res.status == FOUND
    else:
        assert res.status == METHOD_NOT_ALLOWED
        assert set(res.allowed) == {"GET", "POST"}
