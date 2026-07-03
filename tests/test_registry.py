"""Route resolution: versions, dynamic segments, static priority, 404/405."""

from __future__ import annotations

from pathlib import Path

from endocore.core.discovery import RouteSpec, Segment
from endocore.core.registry import Registry, HandlerEntry, FOUND, NOT_FOUND, METHOD_NOT_ALLOWED


def _entry(version, method, *segments):
    segs = tuple(Segment.parse(s) for s in segments)
    spec = RouteSpec(version=version, method=method, segments=segs, file=Path("x"))
    return HandlerEntry(spec=spec, handler=lambda r: None, is_async=False)


def _registry():
    reg = Registry()
    reg.add(_entry("v1", "GET", "User", "Role"))
    reg.add(_entry("v1", "POST", "User", "Role"))
    reg.add(_entry("v1", "GET", "User", "[id]"))
    reg.add(_entry("v2", "GET", "User", "Role"))
    return reg


def test_static_route():
    res = _registry().resolve("GET", "/v1/user/role")
    assert res.status == FOUND and res.match.params == {}


def test_dynamic_capture():
    res = _registry().resolve("GET", "/v1/user/42")
    assert res.status == FOUND and res.match.params == {"id": "42"}


def test_static_beats_dynamic():
    # /v1/user/role must hit the static Role node, not the [id] param.
    res = _registry().resolve("GET", "/v1/user/role")
    assert res.match.params == {}


def test_missing_version_is_404():
    assert _registry().resolve("GET", "/user/role").status == NOT_FOUND


def test_unknown_version_is_404():
    assert _registry().resolve("GET", "/v9/user/role").status == NOT_FOUND


def test_method_not_allowed():
    res = _registry().resolve("DELETE", "/v1/user/role")
    assert res.status == METHOD_NOT_ALLOWED
    assert res.allowed == ("GET", "POST")


def test_versions_isolated():
    reg = _registry()
    # v2 defines only GET on user/role -> POST is 405 there (path exists, no POST)...
    assert reg.resolve("POST", "/v2/user/role").status == METHOD_NOT_ALLOWED
    # ...while v1 has its own POST, untouched by v2.
    assert reg.resolve("POST", "/v1/user/role").status == FOUND
    # A path that exists only in v1 is absent from v2 entirely.
    assert reg.resolve("GET", "/v2/user/42").status == NOT_FOUND


def test_len_counts_handlers():
    assert len(_registry()) == 4
