# Конфигурация

Порты, адреса баз, секреты — настройки обычно живут в переменных окружения.
`Settings` читает их за вас: объявите поля с типами и значениями по умолчанию —
получите готовые распарсенные значения.

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

settings = AppSettings()   # читает DEBUG, DB_URL, PORT, ALLOWED_HOSTS, DATA_DIR из env
```

- Каждый атрибут читается из переменной окружения **В ВЕРХНЕМ РЕГИСТРЕ**,
  приводится к типу аннотации, при отсутствии — берётся объявленный default.
- Поддерживаемые приведения: `bool` (`1/true/yes/on`), `int`, `float`, `Path`,
  `list`/`tuple`/`set` (через запятую), `str`.
- Переопределение при создании: `AppSettings(port=9000)`.
- Поля, в имени которых есть `secret`, `password`, `passwd`, `token`, `key`
  или `dsn`, **маскируются** в `repr`, так что настройки не утекают в логи.

Добавьте префикс, если нужны переменные с пространством имён:

```python
class AppSettings(Settings):
    _env_prefix = "APP_"      # читает APP_DEBUG, APP_PORT, ...
    debug: bool = False
```

Отдайте его через [DI](dependency-injection.md):

```python
# providers.py
from Config import AppSettings
providers = {AppSettings: AppSettings}
```

## Файлы `.env`

```python
from endocore import load_dotenv
load_dotenv(".env")           # строки KEY=VALUE -> os.environ (не перезапишет существующие)
```

## Хелпер `env()`

```python
from endocore import env
env("PORT", default=8000, cast=int)
env("DEBUG", cast=lambda v: v.lower() in {"1", "true", "yes"})
```

## Опции приложения

`Application` (создаётся `end dev` / ASGI-фабрикой) принимает:

| Опция | По умолчанию | Значение |
|--------|---------|---------|
| `dev` | `False` | включить перезагрузку в процессе |
| `default_version` | `None` | `"latest"` резолвит пути без версии |
| `max_body_size` | 16 МБ | отклонять более крупные тела запросов (413) |
| `openapi` | `None` | отдавать `/openapi.json` и `/docs`; `None` = только при `dev=True` (в проде включайте явно: `openapi=True` / `ENDOCORE_OPENAPI=1`) |
| `openapi_title` | `"EndoCore API"` | заголовок в схеме |

`end dev` выносит основные из них во флаги (`--default-version`, `--no-reload`).
