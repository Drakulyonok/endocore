# Configuration

A typed, environment-backed `Settings` object plus small helpers.

## Settings

```python
from endocore import Settings
from pathlib import Path

class AppSettings(Settings):
    debug: bool = False
    db_url: str = "sqlite://app.db"
    port: int = 8000
    allowed_hosts: list = []
    data_dir: Path = Path(".")

settings = AppSettings()   # reads DEBUG, DB_URL, PORT, ALLOWED_HOSTS, DATA_DIR from env
```

- Each attribute is read from the **UPPERCASED** environment variable, cast to
  its annotation, falling back to the declared default.
- Supported casts: `bool` (`1/true/yes/on`), `int`, `float`, `Path`,
  `list`/`tuple`/`set` (comma-separated), `str`.
- Override at construction: `AppSettings(port=9000)`.
- Secret-looking fields (`password`, `token`, `secret`, `key`, …) are **masked**
  in `repr`, so settings never leak into logs.

Add a prefix if you want namespaced vars:

```python
class AppSettings(Settings):
    _env_prefix = "APP_"      # reads APP_DEBUG, APP_PORT, ...
    debug: bool = False
```

Expose it via [DI](dependency-injection.md):

```python
# providers.py
from Config import AppSettings
providers = {AppSettings: AppSettings}
```

## `.env` files

```python
from endocore import load_dotenv
load_dotenv(".env")           # KEY=VALUE lines -> os.environ (won't override existing)
```

## `env()` helper

```python
from endocore import env
env("PORT", default=8000, cast=int)
env("DEBUG", cast=lambda v: v.lower() in {"1", "true", "yes"})
```

## Application options

`Application` (built by `end dev` / the ASGI factory) accepts:

| Option | Default | Meaning |
|--------|---------|---------|
| `dev` | `False` | enable the in-process reload watcher |
| `default_version` | `None` | `"latest"` resolves version-less paths |
| `max_body_size` | 16 MB | reject larger request bodies (413) |
| `openapi` | `True` | serve `/openapi.json` and `/docs` |
| `openapi_title` | `"EndoCore API"` | title in the schema |

`end dev` exposes the common ones as flags (`--default-version`, `--no-reload`).
