"""Property-style coverage for signed values (cookies)."""

from __future__ import annotations

import pytest

from endocore.core.signing import BadSignature, Signer

_VALUES = (
    [f"session-{i}" for i in range(60)]
    + ["", "a", "unicode-héllo", "with.dots.inside", "spaces here", "🚀emoji", "x" * 500]
)


@pytest.mark.parametrize("value", _VALUES)
def test_sign_unsign_roundtrip(value):
    signer = Signer("secret-key")
    assert signer.unsign(signer.sign(value)) == value


@pytest.mark.parametrize("value", _VALUES[:40])
def test_wrong_key_fails(value):
    token = Signer("key-a").sign(value)
    with pytest.raises(BadSignature):
        Signer("key-b").unsign(token)


@pytest.mark.parametrize("value", _VALUES[:40])
def test_wrong_salt_fails(value):
    token = Signer("k", salt="salt-a").sign(value)
    with pytest.raises(BadSignature):
        Signer("k", salt="salt-b").unsign(token)


@pytest.mark.parametrize("pos", list(range(0, 40)))
def test_tamper_detected(pos):
    signer = Signer("secret")
    token = signer.sign("payload-value-that-is-long-enough")
    if pos >= len(token):
        pytest.skip("position beyond token")
    flipped = "A" if token[pos] != "A" else "B"
    tampered = token[:pos] + flipped + token[pos + 1:]
    if tampered == token:
        pytest.skip("no change")
    with pytest.raises(BadSignature):
        signer.unsign(tampered)


@pytest.mark.parametrize("value", ["notoken", "one.part", "only.two", "...", "a.b"])
def test_malformed_rejected(value):
    with pytest.raises(BadSignature):
        Signer("secret").unsign(value)


@pytest.mark.parametrize("obj", [
    {}, {"user": 1}, {"roles": ["a", "b"]}, [1, 2, 3], "string", 42, True,
    {"nested": {"deep": [1, {"x": "y"}]}}, {"unicode": "héllo 🚀"},
])
def test_dumps_loads_roundtrip(obj):
    signer = Signer("secret")
    assert signer.loads(signer.dumps(obj)) == obj


@pytest.mark.parametrize("max_age", [100, 3600, 86400])
def test_fresh_within_max_age(max_age):
    signer = Signer("secret")
    token = signer.sign("v")
    # Just signed -> age ~0, within any non-negative max_age.
    assert signer.unsign(token, max_age=max_age) == "v"
