# Deployment

EndoCore is a standard ASGI app served by `uvicorn`. Anything that runs ASGI
runs EndoCore.

## The ASGI entry point

```python
# provided by the package
endocore.asgi:create_app        # a factory that builds an Application from the CWD
```

`create_app()` reads the current working directory as the app root and honours
three env vars:

- `ENDOCORE_DEV=0` — disable the in-process dev watcher (also switches
  `/docs` + `/openapi.json` off, since they default to "on in dev only").
- `ENDOCORE_DEFAULT_VERSION=latest` — resolve version-less paths.
- `ENDOCORE_OPENAPI=1` — serve `/docs` + `/openapi.json` even with
  `ENDOCORE_DEV=0`. Off by default in production on purpose — opt in
  explicitly if you want the schema/UI publicly reachable.

## Uvicorn (single process)

```bash
uvicorn endocore.asgi:create_app --factory --host 0.0.0.0 --port 8000
```

## Uvicorn workers via Gunicorn (multi-process)

```bash
pip install gunicorn
gunicorn "endocore.asgi:create_app()" \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 --bind 0.0.0.0:8000
```

Rule of thumb: `workers = 2 × CPU cores + 1`. Because the ORM offloads to a
threadpool, workers keep the event loop free under DB load.

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

For production, prefer Gunicorn + Uvicorn workers:

```dockerfile
CMD ["gunicorn", "endocore.asgi:create_app()", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", "--bind", "0.0.0.0:8000"]
```

## Nginx reverse proxy

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

Then trust the proxy headers in your app:

```python
from endocore.middleware import proxy_headers_middleware
middlewares = [proxy_headers_middleware(trusted=["127.0.0.1"])]
```

## systemd service

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

## Migrations on deploy

Run migrations before switching traffic:

```bash
endo migrate            # apply pending migrations
endo showmigrations     # verify
```

## PaaS (Render / Railway / Fly.io / Heroku-style)

- **Build**: `pip install -r requirements.txt`
- **Start**: `gunicorn endocore.asgi:create_app() --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`
- **Env**: `ENDOCORE_DEV=0`, your `DATABASE_URL`, secrets for cookies/CSRF and
  `ENDOCORE_FILE_KEY`.

## Production checklist

- [ ] `ENDOCORE_DEV=0` (no watcher; also turns `/docs` off by default).
- [ ] Leave `ENDOCORE_OPENAPI` unset unless you deliberately want the schema
  public — don't set it to "1" out of habit.
- [ ] Multiple workers behind a proxy.
- [ ] `endo migrate` on each release.
- [ ] Secrets from env (cookie/CSRF secret, `ENDOCORE_FILE_KEY`, DB creds).
- [ ] Security middleware enabled (see [Security](guide/security.md)).
- [ ] TLS terminated at the proxy; `proxy_headers_middleware` configured.
