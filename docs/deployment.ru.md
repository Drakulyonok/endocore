# Развёртывание

EndoCore — стандартное ASGI-приложение, обслуживаемое `uvicorn`. Всё, что умеет
запускать ASGI, запускает EndoCore.

## Точка входа ASGI

```python
# поставляется пакетом
endocore.asgi:create_app        # фабрика, собирающая Application из текущей директории
```

`create_app()` берёт текущую рабочую директорию как корень приложения и
учитывает три переменные окружения:

- `ENDOCORE_DEV=1` — включить dev-режим (вотчер файлов в процессе, `/docs` +
  `/openapi.json`, и ослабленная same-origin проверка websocket для
  локального фронтенда на другом порту). `endo dev` выставляет её сам; голый
  `uvicorn endocore.asgi:create_app --factory` вообще без переменных окружения
  по умолчанию **выключен** — dev-режим включается явно, а не выключается, так
  что забытая переменная падает в сторону более безопасного продакшен-поведения.
- `ENDOCORE_DEFAULT_VERSION=latest` — резолвить пути без версии.
- `ENDOCORE_OPENAPI=1` — отдавать `/docs` + `/openapi.json` даже при
  выключенном dev-режиме. По умолчанию в продакшене выключено намеренно —
  включайте явно, если действительно хотите публичную схему/UI.

## Uvicorn (один процесс)

```bash
uvicorn endocore.asgi:create_app --factory --host 0.0.0.0 --port 8000
```

## Uvicorn-воркеры через Gunicorn (несколько процессов)

```bash
pip install gunicorn
gunicorn "endocore.asgi:create_app()" \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 --bind 0.0.0.0:8000
```

Эмпирическое правило: `workers = 2 × ядра CPU + 1`. Поскольку ORM выгружается в
тредпул, воркеры держат event loop свободным под нагрузкой на БД.

## Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV ENDOCORE_DEV=0
EXPOSE 8000
CMD ["uvicorn", "endocore.asgi:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

`requirements.txt`:

```text
endocore[postgres,files,redis,pydantic]
gunicorn
```

Для продакшена предпочитайте Gunicorn + Uvicorn-воркеры:

```dockerfile
CMD ["gunicorn", "endocore.asgi:create_app()", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", "--bind", "0.0.0.0:8000"]
```

## Обратный прокси Nginx

```nginx
server {
    listen 80;
    server_name api.example.com;
    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_set_header   X-Request-ID      $request_id;
    }
    location /ws/ {                      # websockets
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade    $http_upgrade;
        proxy_set_header   Connection "upgrade";
    }
}
```

Затем доверьтесь заголовкам прокси в приложении:

```python
from endocore.middleware import proxy_headers_middleware
middlewares = [proxy_headers_middleware(trusted=["127.0.0.1"])]
```

## Сервис systemd

```ini
# /etc/systemd/system/endocore.service
[Unit]
Description=EndoCore app
After=network.target

[Service]
WorkingDirectory=/srv/app
Environment=ENDOCORE_DEV=0
ExecStart=/srv/app/.venv/bin/gunicorn endocore.asgi:create_app() \
  --worker-class uvicorn.workers.UvicornWorker --workers 4 --bind 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now endocore
```

## Миграции при деплое

Прогоняйте миграции до переключения трафика:

```bash
endo migrate            # применить ожидающие миграции
endo showmigrations     # проверить
```

## PaaS (Render / Railway / Fly.io / в духе Heroku)

- **Build**: `pip install -r requirements.txt`
- **Start**: `gunicorn endocore.asgi:create_app() --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`
- **Env**: ваш `DATABASE_URL`, секреты для cookies/CSRF и `ENDOCORE_FILE_KEY`
  (dev-режим по умолчанию выключен — `ENDOCORE_DEV` не нужен, если только не
  хотите включить его специально).

## Чек-лист для продакшена

- [ ] Не выставляйте `ENDOCORE_DEV=1` (он и так выключен по умолчанию; без
  вотчера, `/docs` выключен).
- [ ] `ENDOCORE_OPENAPI` оставлен невыставленным, если только сознательно не
  хотите публичную схему — не ставьте "1" по привычке.
- [ ] Несколько воркеров за прокси.
- [ ] `endo migrate` на каждом релизе.
- [ ] Секреты из env (секрет cookie/CSRF, `ENDOCORE_FILE_KEY`, доступы к БД).
- [ ] Включены security-middleware (см. [Безопасность](guide/security.md)).
- [ ] TLS терминируется на прокси; настроен `proxy_headers_middleware`.
