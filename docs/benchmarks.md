# Benchmarks

!!! warning "Read the methodology"
    Benchmarks are easy to fake. These are **in-process ASGI dispatch**
    micro-benchmarks — they isolate *framework overhead* (routing + request
    parsing + response building) by calling each app's ASGI `__call__` directly,
    with **no network**. In production, the HTTP transport (`uvicorn`) and your
    own handler/DB work dominate; framework overhead is a small slice. Numbers
    are reproducible with the script below.

## Method

- Each app exposes a static route (`GET /v1/ping` → `{"pong": true}`) and a
  dynamic route (`GET /v1/item/{id}`).
- We drive the app's ASGI callable `N` times after a 1,000-iteration warm-up and
  measure requests/second and µs/request.
- Compared against **FastAPI/Starlette** with equivalent endpoints.

Run it yourself:

```bash
pip install endocore fastapi
py -3 benchmarks/bench.py 50000
```

## Results

Machine: **Python 3.13.2 · Windows · AMD64** (your numbers will differ; ratios
matter more than absolutes).

| Route | EndoCore | FastAPI/Starlette | Ratio |
|-------|---------:|------------------:|:-----:|
| Static  `GET /v1/ping`        | **≈ 23,700 req/s** | ≈ 29,700 req/s | 0.80× |
| Dynamic `GET /v1/item/{id}`   | **≈ 24,100 req/s** | ≈ 22,500 req/s | **1.07×** |

**Takeaways (honest):**

- On a trivial static route FastAPI's hyper-optimized response path is a bit
  faster (~0.8×).
- On **dynamic routes** EndoCore's trie resolver is slightly **faster** (~1.07×).
- Both frameworks are in the same order of magnitude. At these speeds
  (tens of thousands of req/s of *pure dispatch*), the framework is **never**
  your bottleneck — your database, serialization and network are.

## Why EndoCore is competitive

- The route tree is a **trie built once at boot** and cached; resolution is a
  single walk, no regex-per-request.
- The common `handler(request)` shape uses a **fast path** that skips dependency
  resolution entirely.
- `Request` is a thin object over the raw ASGI scope; headers/query are parsed
  once, body is lazy.

## What this does *not* measure

- Real network throughput (that's `uvicorn`, shared by both).
- JSON serialization of large payloads.
- Database latency (the real bottleneck in most apps — use the
  [async ORM](orm/async.md) to keep the event loop free).

If you need end-to-end HTTP numbers, put either app behind `uvicorn` and load it
with `wrk`/`bombardier` — you'll find both dominated by the transport, not the
framework.
