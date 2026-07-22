"""Dispatch threading, rate-limiter eviction and the OpenAPI serving default.

Regression suite for the review fixes:
- sync handlers run in a worker thread, so a blocking body cannot stall the
  event loop (async handlers stay on the loop);
- the rate limiter sweeps expired client windows instead of growing forever;
- /docs and /openapi.json are served only in dev unless explicitly enabled.
"""

from __future__ import annotations

import asyncio
import types

import pytest

from endocore.core.application import Application
from tests.conftest import call


def _write_handler(root, rel: str, body: str) -> None:
    path = root / "Api" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


# -- sync handlers are offloaded to a worker thread ------------------------

@pytest.fixture()
def loop_app(tmp_path):
    _write_handler(tmp_path, "v1/Sync/Get.py", (
        "import asyncio\n"
        "from endocore import Response\n"
        "def handler(request):\n"
        "    try:\n"
        "        asyncio.get_running_loop()\n"
        "        on_loop = True\n"
        "    except RuntimeError:\n"
        "        on_loop = False\n"
        "    return Response.json({'on_loop': on_loop})\n"
    ))
    _write_handler(tmp_path, "v1/Async/Get.py", (
        "import asyncio\n"
        "from endocore import Response\n"
        "async def handler(request):\n"
        "    asyncio.get_running_loop()\n"
        "    return Response.json({'on_loop': True})\n"
    ))
    _write_handler(tmp_path, "v1/SyncDi/Get.py", (
        "import asyncio\n"
        "from endocore import Response\n"
        "def handler(request, page: str = 'none'):\n"
        "    try:\n"
        "        asyncio.get_running_loop()\n"
        "        on_loop = True\n"
        "    except RuntimeError:\n"
        "        on_loop = False\n"
        "    return Response.json({'on_loop': on_loop})\n"
    ))
    return Application(app_dir=tmp_path)


def test_sync_handler_runs_off_the_event_loop(loop_app):
    status, body, _ = call(loop_app, "GET", "/v1/sync")
    assert status == 200
    assert b'"on_loop": false' in body


def test_sync_handler_with_di_runs_off_the_event_loop(loop_app):
    status, body, _ = call(loop_app, "GET", "/v1/syncdi")
    assert status == 200
    assert b'"on_loop": false' in body


def test_async_handler_stays_on_the_event_loop(loop_app):
    status, body, _ = call(loop_app, "GET", "/v1/async")
    assert status == 200
    assert b'"on_loop": true' in body


def test_sync_background_task_runs_off_the_event_loop(loop_app):
    seen = {}

    def task():
        try:
            asyncio.get_running_loop()
            seen["on_loop"] = True
        except RuntimeError:
            seen["on_loop"] = False

    asyncio.run(loop_app._run_background(task))
    assert seen == {"on_loop": False}


# -- rate limiter eviction --------------------------------------------------

def test_rate_limit_evicts_expired_windows(monkeypatch):
    import endocore.middleware.ratelimit as rl

    now = [1000.0]
    monkeypatch.setattr(rl.time, "monotonic", lambda: now[0])

    middleware = rl.rate_limit_middleware(limit=100, window=60)
    hits = next(
        cell.cell_contents
        for cell in middleware.__closure__
        if isinstance(cell.cell_contents, dict)
    )

    async def call_next(request):
        return "ok"

    def request_from(ip: str):
        return types.SimpleNamespace(scope={"client": (ip, 12345)})

    async def drive():
        for i in range(50):
            await middleware(request_from(f"10.0.0.{i}"), call_next)
        assert len(hits) == 50

        now[0] += 120  # all windows expire
        await middleware(request_from("10.1.1.1"), call_next)  # triggers sweep
        assert len(hits) == 1  # only the fresh client remains

    asyncio.run(drive())


# -- OpenAPI serving default ------------------------------------------------

def _docs_status(app) -> int:
    status, _, _ = call(app, "GET", "/openapi.json")
    return status


@pytest.fixture()
def bare_root(tmp_path):
    _write_handler(tmp_path, "v1/Ping/Get.py", (
        "from endocore import Response\n"
        "async def handler(request):\n    return Response.json({})\n"
    ))
    return tmp_path


def test_docs_off_by_default_in_production(bare_root):
    assert _docs_status(Application(app_dir=bare_root)) == 404


def test_docs_on_in_dev(bare_root):
    # dev=True would also start the file watcher on lifespan; plain HTTP calls
    # here never enter the lifespan scope, so no watcher task is created.
    assert _docs_status(Application(app_dir=bare_root, dev=True)) == 200


def test_docs_explicit_opt_in(bare_root):
    assert _docs_status(Application(app_dir=bare_root, openapi=True)) == 200


def test_docs_explicit_opt_out_in_dev(bare_root):
    assert _docs_status(Application(app_dir=bare_root, dev=True, openapi=False)) == 404
