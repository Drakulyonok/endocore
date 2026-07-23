# The `endo` CLI

Everything you need to scaffold, run, inspect and migrate a project. The CLI is
installed with the package (`pip install endocore`).

```bash
endo --help
endo --version
```

!!! warning "PowerShell: use `endo`"
    `endo` is a reserved keyword in PowerShell, so a bare `endo dev` is a parser
    error there. Use the identical alias **`endo`** (`endo dev`, `endo routes`,
    …) — or `endo.exe dev`. In bash, cmd and zsh both names work.

## Project & endpoints

| Command | Does |
|---------|------|
| `endo new <Name>` | scaffold a new project directory |
| `endo create <path> [method]` | scaffold an endpoint, e.g. `endo create user/role post` |
| `endo create v2/user/[id] get` | scaffold into a specific version, with a dynamic segment |

## Running

| Command | Does |
|---------|------|
| `endo dev` | run the dev server (in-process reload watcher) |
| `endo dev --host 0.0.0.0 --port 8080` | bind host/port |
| `endo dev --no-reload` | disable the watcher |
| `endo dev --default-version latest` | resolve version-less paths to the newest version |

## Inspecting

| Command | Does |
|---------|------|
| `endo routes` | list every method + URL + the file it maps to |
| `endo check` | duplicate routes, broken handlers, skipped files |
| `endo doctor` | Python version, optional deps, project layout checks |
| `endo openapi [--out openapi.json]` | print or write the OpenAPI schema |

## Versions

| Command | Does |
|---------|------|
| `endo version create 2` | copy the latest version → `v2` |
| `endo version create 2 --from 1` | branch from a specific version |
| `endo version create 2 --empty` | scaffolds without bodies |
| `endo version list` | list existing versions |

## Migrations

| Command | Does |
|---------|------|
| `endo makemigrations [name]` | generate a migration from model changes |
| `endo makemigrations --rename table.old=new` | include an explicit column rename |
| `endo makemigrations <name> --python` | write an empty `forward()`/`reverse()` data migration |
| `endo migrate [target]` | apply pending migrations (up to `target`) |
| `endo rollback [--steps N]` | undo the last N migrations |
| `endo showmigrations` | `[x]` applied / `[ ]` pending |
| `endo sqlmigrate <name>` | print a migration's forward SQL |

## Tests

| Command | Does |
|---------|------|
| `endo test` | run the project's tests via pytest |
| `endo test -q -k name` | pytest flags are passed straight through |

!!! tip "Also runnable as a module"
    `python -m endocore <command>` is equivalent to `endo <command>` — handy on
    Windows where a bare `python`/`endo` shim may be missing (`py -3 -m endocore …`).
