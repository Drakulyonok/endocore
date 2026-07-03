"""Small request/response data structures: query params, forms, uploads.

The multipart parser is written from the stdlib (``cgi.FieldStorage`` was removed
in Python 3.13). It buffers the whole body — fine for API-sized uploads; large
streaming uploads are out of scope for this beta.
"""

from __future__ import annotations

from typing import Any, Iterator
from urllib.parse import parse_qs


class MultiDict:
    """A read-only mapping where each key may have several values.

    Indexing / ``get`` return the **first** value (the common case); ``getlist``
    returns them all.
    """

    def __init__(self, data: dict[str, list[Any]] | None = None) -> None:
        self._dict: dict[str, list[Any]] = data or {}

    def __getitem__(self, key: str) -> Any:
        values = self._dict.get(key)
        if not values:
            raise KeyError(key)
        return values[0]

    def get(self, key: str, default: Any = None) -> Any:
        values = self._dict.get(key)
        return values[0] if values else default

    def getlist(self, key: str) -> list[Any]:
        return list(self._dict.get(key, []))

    def __contains__(self, key: str) -> bool:
        return key in self._dict

    def __iter__(self) -> Iterator[str]:
        return iter(self._dict)

    def keys(self):
        return self._dict.keys()

    def items(self):
        return [(k, v[0]) for k, v in self._dict.items() if v]

    def __len__(self) -> int:
        return len(self._dict)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.items()!r})"


class QueryParams(MultiDict):
    """Parsed URL query string."""

    def __init__(self, query_string: str | bytes = "") -> None:
        if isinstance(query_string, bytes):
            query_string = query_string.decode("latin-1")
        super().__init__(parse_qs(query_string, keep_blank_values=True))


class UploadFile:
    """An uploaded file from a multipart form (buffered in memory)."""

    def __init__(self, filename: str, content_type: str, content: bytes) -> None:
        self.filename = filename
        self.content_type = content_type
        self._content = content

    def read(self) -> bytes:
        return self._content

    @property
    def size(self) -> int:
        return len(self._content)

    def __repr__(self) -> str:
        return f"<UploadFile {self.filename!r} {self.size}B>"


class FormData(MultiDict):
    """Submitted form fields. Text values are ``str``; files are ``UploadFile``."""

    @property
    def files(self) -> dict[str, UploadFile]:
        return {k: v[0] for k, v in self._dict.items() if v and isinstance(v[0], UploadFile)}


def parse_urlencoded(body: bytes) -> FormData:
    return FormData(parse_qs(body.decode("utf-8"), keep_blank_values=True))


def _parse_disposition(value: str) -> dict[str, str]:
    params: dict[str, str] = {}
    for chunk in value.split(";"):
        chunk = chunk.strip()
        if "=" in chunk:
            key, _, raw = chunk.partition("=")
            params[key.strip().lower()] = raw.strip().strip('"')
    return params


def parse_multipart(body: bytes, boundary: str) -> FormData:
    """Parse a ``multipart/form-data`` body into fields and uploaded files."""
    data: dict[str, list[Any]] = {}
    delimiter = b"--" + boundary.encode("latin-1")

    for raw_part in body.split(delimiter):
        part = raw_part.strip(b"\r\n")
        if not part or part == b"--":
            continue  # preamble / closing delimiter
        head, _, content = part.partition(b"\r\n\r\n")

        disposition = ""
        content_type = "text/plain"
        for line in head.split(b"\r\n"):
            name, _, val = line.partition(b":")
            key = name.decode("latin-1").strip().lower()
            if key == "content-disposition":
                disposition = val.decode("latin-1").strip()
            elif key == "content-type":
                content_type = val.decode("latin-1").strip()

        params = _parse_disposition(disposition)
        field = params.get("name")
        if field is None:
            continue

        if "filename" in params:
            value: Any = UploadFile(params["filename"], content_type, content)
        else:
            value = content.decode("utf-8")
        data.setdefault(field, []).append(value)

    return FormData(data)
