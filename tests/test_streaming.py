"""StreamingResponse and Request.stream()."""

from __future__ import annotations

import asyncio

from endocore import Request, StreamingResponse


def _collect(response):
    sent = []

    async def send(message):
        sent.append(message)

    asyncio.run(response(send))
    return sent


def test_streaming_sync_iterable():
    sent = _collect(StreamingResponse([b"a", b"bc", "d"], media_type="text/plain"))
    start = sent[0]
    bodies = [m for m in sent if m["type"] == "http.response.body"]
    assert start["status"] == 200
    assert b"".join(m["body"] for m in bodies) == b"abcd"
    assert bodies[-1]["more_body"] is False


def test_streaming_async_iterable():
    async def agen():
        yield b"x"
        yield b"y"

    sent = _collect(StreamingResponse(agen()))
    body = b"".join(m["body"] for m in sent if m["type"] == "http.response.body")
    assert body == b"xy"


def test_request_stream_reads_chunks():
    chunks = [
        {"type": "http.request", "body": b"he", "more_body": True},
        {"type": "http.request", "body": b"llo", "more_body": False},
    ]

    async def receive():
        return chunks.pop(0)

    request = Request(
        {"type": "http", "method": "POST", "path": "/", "query_string": b"", "headers": []},
        receive,
    )

    async def run():
        out = b""
        async for chunk in request.stream():
            out += chunk
        return out

    assert asyncio.run(run()) == b"hello"
