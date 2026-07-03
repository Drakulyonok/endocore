"""In-process ASGI dispatch micro-benchmark: EndoCore vs FastAPI/Starlette.

This measures *framework overhead* — routing + request parsing + response
building — by calling each app's ASGI ``__call__`` directly, N times, with no
network. The HTTP transport (uvicorn) is identical for both, so isolating the
framework layer is the fair comparison.

Run:  py -3 benchmarks/bench.py [iterations]
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path


def _make_endocore():
    from endocore.core.application import Application

    root = Path(__file__).parent / "_bench_app"
    (root / "Api" / "v1" / "Ping").mkdir(parents=True, exist_ok=True)
    (root / "Api" / "v1" / "Ping" / "Get.py").write_text(
        "from endocore import Response\n"
        "async def handler(request):\n    return Response.json({'pong': True})\n",
        encoding="utf-8",
    )
    (root / "Api" / "v1" / "Item" / "[id]").mkdir(parents=True, exist_ok=True)
    (root / "Api" / "v1" / "Item" / "[id]" / "Get.py").write_text(
        "from endocore import Response\n"
        "async def handler(request):\n"
        "    return Response.json({'id': request.path_params['id']})\n",
        encoding="utf-8",
    )
    return Application(app_dir=root, openapi=False)


def _make_fastapi():
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/v1/ping")
    async def ping():
        return {"pong": True}

    @app.get("/v1/item/{id}")
    async def item(id: str):
        return {"id": id}

    return app


def _http_scope(path: str) -> dict:
    return {
        "type": "http", "method": "GET", "path": path, "raw_path": path.encode(),
        "query_string": b"", "headers": [], "client": ("127.0.0.1", 0), "server": ("127.0.0.1", 8000),
        "scheme": "http", "http_version": "1.1", "asgi": {"version": "3.0", "spec_version": "2.3"},
    }


async def _drive(app, path: str) -> None:
    scope = _http_scope(path)
    done = asyncio.Event()

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        if message["type"] == "http.response.body" and not message.get("more_body"):
            done.set()

    await app(scope, receive, send)


async def _bench(name: str, app, path: str, n: int) -> float:
    # warm-up
    for _ in range(1000):
        await _drive(app, path)
    start = time.perf_counter()
    for _ in range(n):
        await _drive(app, path)
    elapsed = time.perf_counter() - start
    rps = n / elapsed
    us = elapsed / n * 1e6
    print(f"  {name:<24} {rps:>12,.0f} req/s   {us:>8.2f} µs/req")
    return rps


async def main(n: int) -> None:
    endo = _make_endocore()
    fast = _make_fastapi()

    print(f"\nIn-process ASGI dispatch, {n:,} iterations (higher req/s is better)\n")
    print("Static route  GET /v1/ping")
    e1 = await _bench("EndoCore", endo, "/v1/ping", n)
    f1 = await _bench("FastAPI/Starlette", fast, "/v1/ping", n)
    print(f"  -> EndoCore is {e1 / f1:.2f}x FastAPI here\n")

    print("Dynamic route GET /v1/item/{id}")
    e2 = await _bench("EndoCore", endo, "/v1/item/42", n)
    f2 = await _bench("FastAPI/Starlette", fast, "/v1/item/42", n)
    print(f"  -> EndoCore is {e2 / f2:.2f}x FastAPI here\n")

    import platform
    print(f"Python {platform.python_version()} · {platform.system()} · "
          f"{platform.processor() or 'cpu'}")


if __name__ == "__main__":
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 50000
    asyncio.run(main(iterations))
