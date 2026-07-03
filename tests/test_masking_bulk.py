"""Property-style coverage for sensitive-data masking."""

from __future__ import annotations

import pytest

from endocore.core.logging import MASK, SENSITIVE_KEYS, mask


@pytest.mark.parametrize("key", sorted(SENSITIVE_KEYS))
def test_each_sensitive_key_masked(key):
    assert mask({key: "value"}) == {key: MASK}


@pytest.mark.parametrize("key", sorted(SENSITIVE_KEYS))
@pytest.mark.parametrize("case", ["upper", "title", "mixed"])
def test_case_insensitive(key, case):
    variant = {"upper": key.upper(), "title": key.title(), "mixed": key.capitalize()}[case]
    assert mask({variant: "x"}) == {variant: MASK}


@pytest.mark.parametrize("safe", ["name", "email", "id", "count", "title", "status", "age", "url"])
def test_non_sensitive_untouched(safe):
    assert mask({safe: "value"}) == {safe: "value"}


@pytest.mark.parametrize("depth", list(range(1, 12)))
def test_nested_masking(depth):
    data: dict = {"password": "secret"}
    for _ in range(depth):
        data = {"wrap": data}
    out = data_out = mask(data)
    for _ in range(depth):
        data_out = data_out["wrap"]
    assert data_out == {"password": MASK}
    assert out is not data  # copy, original preserved


@pytest.mark.parametrize("n", list(range(0, 25)))
def test_list_of_dicts(n):
    data = {"users": [{"password": f"p{i}", "name": f"n{i}"} for i in range(n)]}
    out = mask(data)
    assert all(u["password"] == MASK for u in out["users"])
    assert all(u["name"] == f"n{i}" for i, u in enumerate(out["users"]))


@pytest.mark.parametrize("value", [1, 1.5, True, None, "text", [1, 2, 3], (1, 2)])
def test_passthrough_non_mapping(value):
    assert mask(value) == value


def test_original_not_mutated():
    data = {"password": "x", "nested": {"token": "y"}}
    mask(data)
    assert data == {"password": "x", "nested": {"token": "y"}}
