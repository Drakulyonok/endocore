"""Coverage for QueryParams / MultiDict / form parsers."""

from __future__ import annotations

import pytest

from endocore.core.datastructures import (
    FormData,
    MultiDict,
    QueryParams,
    UploadFile,
    parse_multipart,
    parse_urlencoded,
)


@pytest.mark.parametrize("i", list(range(40)))
def test_queryparams_single(i):
    q = QueryParams(f"page={i}&size=10")
    assert q.get("page") == str(i)
    assert q["page"] == str(i)
    assert q.get("missing") is None
    assert q.get("missing", "d") == "d"


@pytest.mark.parametrize("values", [["a"], ["a", "b"], ["x", "y", "z"], list("abcde")])
def test_queryparams_getlist(values):
    qs = "&".join(f"tag={v}" for v in values)
    q = QueryParams(qs)
    assert q.getlist("tag") == values
    assert q.get("tag") == values[0]


@pytest.mark.parametrize("qs,key,present", [
    ("a=1", "a", True), ("a=1", "b", False), ("", "a", False),
    ("x=1&y=2", "y", True), ("flag=", "flag", True),
])
def test_queryparams_contains(qs, key, present):
    assert (key in QueryParams(qs)) is present


def test_multidict_items_and_len():
    md = MultiDict({"a": [1, 2], "b": [3]})
    assert dict(md.items()) == {"a": 1, "b": 3}
    assert len(md) == 2
    assert md.getlist("a") == [1, 2]


@pytest.mark.parametrize("i", list(range(30)))
def test_urlencoded(i):
    form = parse_urlencoded(f"name=user{i}&age={i}".encode())
    assert form.get("name") == f"user{i}"
    assert form.get("age") == str(i)


@pytest.mark.parametrize("field,value", [
    ("title", "Hello"), ("body", "multi\nline"), ("x", ""), ("u", "héllo"),
    ("special", "a=b&c=d"),
])
def test_multipart_text_field(field, value):
    boundary = "BOUND"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"\r\n\r\n'
        f"{value}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    form = parse_multipart(body, boundary)
    assert form.get(field) == value


@pytest.mark.parametrize("filename,content", [
    ("a.txt", b"hello"), ("bin.dat", b"\x00\x01\x02"), ("empty", b""),
    ("big.bin", b"X" * 5000),
])
def test_multipart_file(filename, content):
    boundary = "B"
    body = (
        b"--B\r\n"
        b'Content-Disposition: form-data; name="file"; filename="' + filename.encode() + b'"\r\n'
        b"Content-Type: application/octet-stream\r\n\r\n" + content + b"\r\n--B--\r\n"
    )
    form = parse_multipart(body, boundary)
    up = form.get("file")
    assert isinstance(up, UploadFile)
    assert up.filename == filename
    assert up.read() == content
    assert up.size == len(content)
    assert form.files["file"] is up


def test_multipart_mixed_fields_and_files():
    boundary = "M"
    body = (
        b"--M\r\nContent-Disposition: form-data; name=\"a\"\r\n\r\n1\r\n"
        b"--M\r\nContent-Disposition: form-data; name=\"f\"; filename=\"x\"\r\n\r\nDATA\r\n"
        b"--M--\r\n"
    )
    form = parse_multipart(body, boundary)
    assert form.get("a") == "1"
    assert form.files["f"].read() == b"DATA"
    assert len(form.files) == 1
