# Contributing

EndoCore is a young, focused project. Contributions that keep it small, secure
and legible are very welcome.

## Development setup

```bash
git clone https://github.com/Drakulyonok/endocore
cd endocore
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[postgres,files,redis,celery,pydantic,watch]"
pip install pytest
pytest -q                                        # 1600+ tests
```

## Principles to respect

- **The core has one dependency** (`uvicorn`). New capabilities that need a
  library go behind an **optional extra**, imported lazily.
- **Security is a default.** ORM values are always bound; identifiers validated
  and quoted; lookups whitelisted. Never build SQL by string-formatting values.
- **Endpoints stay thin.** Logic belongs in services.
- **Everything is tested.** Add tests with every change; the suite runs in
  seconds and uses SQLite in-memory.

## Running things

```bash
pytest -q                       # all tests
pytest tests/orm -q             # a subset
py -3 benchmarks/bench.py       # the dispatch benchmark
mkdocs serve                    # preview the docs locally
```

## Coding style

- Match the surrounding code — comment density, naming, and idiom.
- Public functions get a one-line docstring explaining the contract.
- Prefer standard-library solutions in the core.

## Pull requests

1. Open an issue describing the change first for anything non-trivial.
2. Keep PRs focused; one concern per PR.
3. Include tests and, if user-facing, a docs update and a `CHANGELOG.md` entry.
4. Make sure `pytest -q` is green.

## What we won't merge

- Anything that puts values into SQL without parameter binding.
- New required core dependencies.
- Features that contradict the [philosophy](getting-started/philosophy.md) —
  when in doubt, open an issue first.

## Reporting security issues

Please **do not** open a public issue for a vulnerability. Report it privately to
the maintainer (see the repository's security policy) so it can be fixed before
disclosure.
