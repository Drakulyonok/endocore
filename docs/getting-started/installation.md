# Installation

## Requirements

- **Python 3.11+**
- The only required runtime dependency is **`uvicorn`** (the ASGI server).

## Install from PyPI

```bash
pip install endocore
```

That gives you the full framework, the CLI (`end`), and the ORM for **SQLite**
(SQLite support is built on the standard library — nothing extra to install).

??? tip "New to Python? Use a virtual environment"
    A virtual environment keeps each project's packages separate, so nothing
    breaks system-wide. Create and activate one first:

    ```bash
    python -m venv .venv
    # Windows:
    .venv\Scripts\activate
    # Linux / macOS:
    source .venv/bin/activate

    pip install endocore
    ```

## Optional extras

EndoCore keeps its core tiny; opt into what you need:

| Extra | Installs | Enables |
|-------|----------|---------|
| `postgres` | `psycopg` | PostgreSQL backend for the ORM |
| `files` | `cryptography` | Encrypted `FileField` (AES-256-GCM at rest) |
| `redis` | `redis` | Redis cache backend + `RedisExtension` |
| `celery` | `celery` | `CeleryExtension` task queue integration |
| `pydantic` | `pydantic` | Typed request bodies + richer OpenAPI schemas |
| `watch` | `watchfiles` | In-process dev auto-reload watcher |

```bash
pip install "endocore[postgres,files,pydantic]"
# everything useful in development:
pip install "endocore[postgres,files,redis,celery,pydantic,watch]"
```

## Verify the install

```bash
end --version         # EndoCore 0.7.0b1
end doctor            # environment, dependencies, project checks
```

`end doctor` prints your Python version, which optional dependencies are
present, and whether the current directory looks like an EndoCore project.

## From source (development)

```bash
git clone https://github.com/Drakulyonok/endocore
cd endocore
pip install -e ".[postgres,files,redis,celery,pydantic,watch]"
pip install pytest
pytest -q             # 1600+ tests
```

## Windows notes

**PowerShell:** `end` is a reserved keyword there, so `end dev` won't parse.
Use the identical alias `endo`:

```powershell
endo --version
endo dev
```

**Broken `python` shim:** on some setups a bare `python` doesn't work — use
the launcher:

```bash
py -3 -m pip install endocore
py -3 -m endocore --version     # equivalent to `end --version`
```

Next: the [Quickstart](quickstart.md).
