# Развёртывание

EndoCore — стандартное ASGI-приложение, обслуживаемое `uvicorn`. Всё, что умеет
запускать ASGI, запускает EndoCore.

## Точка входа ASGI

```python
# поставляется пакетом
endocore.asgi:create_app        # фабрика, собирающая Application из текущей директории
```

`create_app()` берёт текущую рабочую директорию как корень приложения и
учитывает две переменные окружения:

- `ENDOCORE_DEV=0` — отключить dev-вотчер в процессе.
- `ENDOCORE_DEFAULT_VERSION=latest` — резолвить пути без версии.

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
end migrate            # применить ожидающие миграции
end showmigrations     # проверить
```

## PaaS (Render / Railway / Fly.io / в духе Heroku)

- **Build**: `pip install -r requirements.txt`
- **Start**: `gunicorn endocore.asgi:create_app() --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`
- **Env**: `ENDOCORE_DEV=0`, ваш `DATABASE_URL`, секреты для cookies/CSRF и
  `ENDOCORE_FILE_KEY`.

## Чек-лист для продакшена

- [ ] `ENDOCORE_DEV=0` (без вотчера).
- [ ] Несколько воркеров за прокси.
- [ ] `end migrate` на каждом релизе.
- [ ] Секреты из env (секрет cookie/CSRF, `ENDOCORE_FILE_KEY`, доступы к БД).
- [ ] Включены security-middleware (см. [Безопасность](guide/security.md)).
- [ ] TLS терминируется на прокси; настроен `proxy_headers_middleware`.
