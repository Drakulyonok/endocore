# Архитектура

EndoCore — тонкий, читаемый конвейер. Эта страница показывает всю систему,
чтобы вы всегда знали, где находится запрос и какой модуль за него отвечает.

## Две половины

```text
endocore/            ← фреймворк (устанавливаемый пакет, CLI `endo`)
your_app/            ← ваше приложение (Api/, Services/, Models/, ...)
```

Вы импортируете `endocore`; вы *пишете* `your_app`. Фреймворк не генерирует вашу
бизнес-логику — он её находит и обслуживает.

## Раскладка пакета

```text
endocore/
  core/
    discovery.py     # обход дерева Api/ -> список RouteSpec (единственный обход)
    router.py        # разбор пути + правила матчинга (версия, [id], метод)
    registry.py      # trie маршрутов + резолвер (строится один раз при старте)
    loader.py        # динамический импорт хендлеров (устойчив к ошибкам)
    request.py       # Request поверх ASGI scope
    response.py      # Response / StreamingResponse -> ASGI send
    websocket.py     # WebSocket поверх ASGI websocket scope
    middleware.py    # onion / цепочка call_next
    di.py            # Depends() + разрешение провайдеров
    application.py   # async def app(scope, receive, send) — всё связывает
    cache.py  config.py  signing.py  pubsub.py  openapi.py  exceptions.py
  middleware/        # поставляемый middleware: logging, cors, csrf, gzip, ...
  orm/               # ORM (models, fields, query, compiler, backends, ...)
  cli/               # CLI `endo` (create, dev, routes, migrate, ...)
  extensions/        # интеграции Redis, Celery, Email, Cache
```

## Последовательность старта

При старте `Application.boot()`:

1. Кладёт директорию приложения в `sys.path` (чтобы работал `from Services...`).
2. **Сканирует** `Api/` один раз через `pathlib.rglob("*.py")` → список `RouteSpec`.
3. **Импортирует** каждый хендлер через `importlib` в `try/except`. Один
   сломанный файл собирается как `BootError`, но не фатален.
4. **Регистрирует** хендлеры в **trie** маршрутов (по версии → сегменту).
5. Загружает пользовательский middleware (`Middleware/__init__.py`), хуки
   (`hooks.py`), DI-провайдеры (`providers.py`) и расширения (`extensions.py`).
6. Строит конвейер один раз и логирует сводку старта
   (`loaded N routes, M files with errors`).

Дерево маршрутов **кэшируется**. В dev-режиме watcher на `watchfiles`
пересобирает его в процессе при изменениях — без рестарта.

## Поток запроса

```text
                ┌─────────────── цепочка middleware (onion) ───────────────┐
scope/receive → │ logging → [ ваш middleware... ] → dispatch → handler → Response│ → send
                └───────────────────────────────────────────────────────────────┘
```

1. `Application.__call__` получает сырой ASGI `(scope, receive, send)`.
2. Для `http` строит `Request` и прогоняет его через **конвейер**.
3. Внутренний слой `_dispatch` резолвит маршрут в trie, внедряет зависимости
   (`di.solve`), вызывает ваш `handler` и приводит возвращённое значение к
   `Response`.
4. `Response` пишет себя в `send`.

`websocket`-scope обрабатывает `_handle_websocket`; `lifespan` запускает хуки
startup/shutdown и dev-watcher.

## Резолвер (сердце) {#the-resolver-the-heart}

Дан `POST /v2/user/42/role`, резолвер:

- разбивает путь на сегменты;
- сверяет первый сегмент с `^v\d+$` → это **версия**;
- проходит trie, предпочитая **статических** потомков **динамическому**
  (`[id]`), захватывая параметры пути;
- ищет **метод** (`POST`) в найденном узле.

Исходы: `200` (найдено), `404` (нет такого пути/версии), `405` (путь есть,
неверный метод). Без префикса версии — по умолчанию `404` (опциональный
алиас "latest"). Подробности всех граничных случаев — на странице
[Роутинг](routing.md).

## Слои в вашем приложении

| Слой | Роль |
|------|------|
| **API** (`Api/`) | файлы-endpoint'ы — тонкие: распарсил → позвал сервис → ответил |
| **Services** | вся бизнес-логика; тяжёлый код здесь |
| **Models** | описание данных (модели ORM) |
| **Middleware** | обвязка запроса (auth, логирование, CORS, ...) |
| **Utils** | чистые функции без побочных эффектов |

Именно это разделение делает версионирование дешёвым: новая версия копирует
тонкие endpoint'ы и *локальные* сервисы, а глобальные `/Services/` остаются
общими.
