# Benchmarks

!!! warning "What this measures"
    Framework overhead only: routing, request parsing, response building. The
    benchmark calls each app's ASGI callable directly, in one process — no
    network, no web server. It says nothing about end-to-end HTTP throughput,
    where `uvicorn` and your database dominate for both frameworks equally.

## Setup

- Two identical endpoints in each framework: static `GET /v1/ping` and dynamic
  `GET /v1/item/{id}`.
- 1,000 warm-up calls, then 50,000 timed calls. Reported numbers are the median
  of 3 runs.
- Request logging is off in both apps, so console I/O isn't part of the timing.
- Both apps were checked to return identical 200 responses before timing.

## Results

Python 3.14.3, Windows 11, AMD Ryzen, FastAPI 0.139. Absolute numbers depend on
the machine — the ratios are what matters.

| Route | EndoCore | FastAPI | Ratio |
|-------|---------:|--------:|:-----:|
| Static `GET /v1/ping` | 23,800 req/s (42 µs) | 11,000 req/s (91 µs) | 2.2× |
| Dynamic `GET /v1/item/{id}` | 30,800 req/s (32 µs) | 8,600 req/s (116 µs) | 3.6× |

## Why the gap

EndoCore resolves a route with one walk over a trie built at boot, and a plain
`handler(request)` skips dependency resolution entirely. FastAPI runs its
validation and serialization machinery even for endpoints that don't use it —
that work buys features, but on a trivial endpoint it's pure overhead. Bare
Starlette would land much closer to EndoCore.

Does the gap matter in practice? Rarely. A dispatch costs 30–120 µs; a single
indexed database query costs more. Pick a framework for its ergonomics, not for
this table.

## Reproduce

```bash
pip install endocore fastapi
python benchmarks/bench.py 50000
```

The script ([benchmarks/bench.py](https://github.com/Drakulyonok/endocore/blob/master/benchmarks/bench.py))
builds both apps, warms them up, and prints req/s and the ratio for each route.

## Not measured

- The HTTP transport — that's `uvicorn`, identical for both.
- Serialization of large JSON payloads — both endpoints return tiny bodies.
- Database latency — the usual real bottleneck; the [async ORM](orm/async.md)
  keeps the event loop free while queries run.
