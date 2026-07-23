# CLI `endo`

Всё для скаффолдинга, запуска, инспекции и миграций проекта. CLI ставится
вместе с пакетом (`pip install endocore`).

```bash
endo --help
endo --version
```

!!! warning "PowerShell: используйте `endo`"
    `endo` — зарезервированное слово PowerShell, поэтому там `endo dev` — ошибка
    парсера. Используйте идентичный алиас **`endo`** (`endo dev`,
    `endo routes`, …) — или `endo.exe dev`. В bash, cmd и zsh работают оба
    имени.

## Проект и endpoint'ы

| Команда | Делает |
|---------|------|
| `endo new <Name>` | создать каркас нового проекта |
| `endo create <path> [method]` | создать endpoint, например `endo create user/role post` |
| `endo create v2/user/[id] get` | создать в конкретной версии, с динамическим сегментом |

## Запуск

| Команда | Делает |
|---------|------|
| `endo dev` | запустить dev-сервер (перезагрузка в процессе) |
| `endo dev --host 0.0.0.0 --port 8080` | задать host/port |
| `endo dev --no-reload` | отключить вотчер |
| `endo dev --default-version latest` | резолвить пути без версии в самую свежую |

## Инспекция

| Команда | Делает |
|---------|------|
| `endo routes` | вывести каждый метод + URL + файл, на который он указывает |
| `endo check` | дубли маршрутов, битые обработчики, пропущенные файлы |
| `endo doctor` | версия Python, опциональные зависимости, проверки структуры |
| `endo openapi [--out openapi.json]` | напечатать или записать OpenAPI-схему |

## Версии

| Команда | Делает |
|---------|------|
| `endo version create 2` | скопировать последнюю версию → `v2` |
| `endo version create 2 --from 1` | ответвиться от конкретной версии |
| `endo version create 2 --empty` | каркас без тел обработчиков |
| `endo version list` | вывести существующие версии |

## Миграции

| Команда | Делает |
|---------|------|
| `endo makemigrations [name]` | сгенерировать миграцию из изменений моделей |
| `endo makemigrations --rename table.old=new` | включить явное переименование колонки |
| `endo makemigrations <name> --python` | создать пустую миграцию данных `forward()`/`reverse()` |
| `endo migrate [target]` | применить ожидающие миграции (до `target`) |
| `endo rollback [--steps N]` | отменить последние N миграций |
| `endo showmigrations` | `[x]` применена / `[ ]` ожидает |
| `endo sqlmigrate <name>` | напечатать forward-SQL миграции |

## Тесты

| Команда | Делает |
|---------|------|
| `endo test` | запустить тесты проекта через pytest |
| `endo test -q -k name` | флаги pytest передаются напрямую |

!!! tip "Можно запускать и как модуль"
    `python -m endocore <command>` эквивалентно `endo <command>` — удобно на
    Windows, где может не быть shim'ов `python`/`endo` (`py -3 -m endocore …`).
