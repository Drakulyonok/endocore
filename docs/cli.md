# The `end` CLI

Everything you need to scaffold, run, inspect and migrate a project. The CLI is
installed with the package (`pip install endocore`).

```bash
end --help
end --version
```

!!! warning "PowerShell: use `endo`"
    `end` is a reserved keyword in PowerShell, so a bare `end dev` is a parser
    error there. Use the identical alias **`endo`** (`endo dev`, `endo routes`,
    …) — or `end.exe dev`. In bash, cmd and zsh both names work.

## Project & endpoints

| Command | Does |
|---------|------|
| `end new <Name>` | scaffold a new project directory |
| `end create <path> [method]` | scaffold an endpoint, e.g. `end create user/role post` |
| `end create v2/user/[id] get` | scaffold into a specific version, with a dynamic segment |

## Running

| Command | Does |
|---------|------|
| `end dev` | run the dev server (in-process reload watcher) |
| `end dev --host 0.0.0.0 --port 8080` | bind host/port |
| `end dev --no-reload` | disable the watcher |
| `end dev --default-version latest` | resolve version-less paths to the newest version |

## Inspecting

| Command | Does |
|---------|------|
| `end routes` | list every method + URL + the file it maps to |
| `end check` | duplicate routes, broken handlers, skipped files |
| `end doctor` | Python version, optional deps, project layout checks |
| `end openapi [--out openapi.json]` | print or write the OpenAPI schema |

## Versions

| Command | Does |
|---------|------|
| `end version create 2` | copy the latest version → `v2` |
| `end version create 2 --from 1` | branch from a specific version |
| `end version create 2 --empty` | scaffolds without bodies |
| `end version list` | list existing versions |

## Migrations

| Command | Does |
|---------|------|
| `end makemigrations [name]` | generate a migration from model changes |
| `end makemigrations --rename table.old=new` | include an explicit column rename |
| `end migrate [target]` | apply pending migrations (up to `target`) |
| `end rollback [--steps N]` | undo the last N migrations |
| `end showmigrations` | `[x]` applied / `[ ]` pending |
| `end sqlmigrate <name>` | print a migration's forward SQL |

## Tests

| Command | Does |
|---------|------|
| `end test` | run the project's tests via pytest |
| `end test -q -k name` | pytest flags are passed straight through |

!!! tip "Also runnable as a module"
    `python -m endocore <command>` is equivalent to `end <command>` — handy on
    Windows where a bare `python`/`end` shim may be missing (`py -3 -m endocore …`).
