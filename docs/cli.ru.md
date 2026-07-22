# CLI `end`

Всё для скаффолдинга, запуска, инспекции и миграций проекта. CLI ставится
вместе с пакетом (`pip install endocore`).

```bash
end --help
end --version
```

!!! warning "PowerShell: используйте `endo`"
    `end` — зарезервированное слово PowerShell, поэтому там `end dev` — ошибка
    парсера. Используйте идентичный алиас **`endo`** (`endo dev`,
    `endo routes`, …) — или `end.exe dev`. В bash, cmd и zsh работают оба
    имени.

## Проект и endpoint'ы

| Команда | Делает |
|---------|------|
| `end new <Name>` | создать каркас нового проекта |
| `end create <path> [method]` | создать endpoint, например `end create user/role post` |
| `end create v2/user/[id] get` | создать в конкретной версии, с динамическим сегментом |

## Запуск

| Команда | Делает |
|---------|------|
| `end dev` | запустить dev-сервер (перезагрузка в процессе) |
| `end dev --host 0.0.0.0 --port 8080` | задать host/port |
| `end dev --no-reload` | отключить вотчер |
| `end dev --default-version latest` | резолвить пути без версии в самую свежую |

## Инспекция

| Команда | Делает |
|---------|------|
| `end routes` | вывести каждый метод + URL + файл, на который он указывает |
| `end check` | дубли маршрутов, битые обработчики, пропущенные файлы |
| `end doctor` | версия Python, опциональные зависимости, проверки структуры |
| `end openapi [--out openapi.json]` | напечатать или записать OpenAPI-схему |

## Версии

| Команда | Делает |
|---------|------|
| `end version create 2` | скопировать последнюю версию → `v2` |
| `end version create 2 --from 1` | ответвиться от конкретной версии |
| `end version create 2 --empty` | каркас без тел обработчиков |
| `end version list` | вывести существующие версии |

## Миграции

| Команда | Делает |
|---------|------|
| `end makemigrations [name]` | сгенерировать миграцию из изменений моделей |
| `end makemigrations --rename table.old=new` | включить явное переименование колонки |
| `end migrate [target]` | применить ожидающие миграции (до `target`) |
| `end rollback [--steps N]` | отменить последние N миграций |
| `end showmigrations` | `[x]` применена / `[ ]` ожидает |
| `end sqlmigrate <name>` | напечатать forward-SQL миграции |

## Тесты

| Команда | Делает |
|---------|------|
| `end test` | запустить тесты проекта через pytest |
| `end test -q -k name` | флаги pytest передаются напрямую |

!!! tip "Можно запускать и как модуль"
    `python -m endocore <command>` эквивалентно `end <command>` — удобно на
    Windows, где может не быть shim'ов `python`/`end` (`py -3 -m endocore …`).
