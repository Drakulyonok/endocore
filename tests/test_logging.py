"""Sensitive-data masking at the logger layer."""

from __future__ import annotations

from endocore.core.logging import mask, MASK


def test_masks_top_level_keys():
    out = mask({"name": "admin", "password": "secret"})
    assert out == {"name": "admin", "password": MASK}


def test_masking_is_case_insensitive():
    out = mask({"Authorization": "Bearer x", "Token": "t"})
    assert out == {"Authorization": MASK, "Token": MASK}


def test_masks_nested_and_lists():
    data = {"users": [{"password": "a"}, {"password": "b"}], "meta": {"secret": "s"}}
    out = mask(data)
    assert out == {"users": [{"password": MASK}, {"password": MASK}], "meta": {"secret": MASK}}


def test_non_dict_passthrough():
    assert mask("hello") == "hello"
    assert mask([1, 2, 3]) == [1, 2, 3]


def test_original_not_mutated():
    data = {"password": "secret"}
    mask(data)
    assert data == {"password": "secret"}
