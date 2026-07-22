# Celery

Выносите медленную или требующую надёжности фоновую работу в очередь задач
Celery.

```bash
pip install "endocore[celery]"     # плюс брокер, например Redis или RabbitMQ
```

## Регистрация Celery-приложения

```python
# extensions.py
from endocore.extensions import CeleryExtension

extensions = [
    CeleryExtension(
        app_name="myapp",
        broker="redis://localhost:6379/1",
        backend="redis://localhost:6379/2",
    ),
]
```

Это регистрирует Celery-приложение как DI-провайдер под именем `celery`.

## Определение задач

```python
# Services/tasks.py
from endocore.extensions import celery_app

app = celery_app("myapp", broker="redis://localhost:6379/1")

@app.task
def send_email(to: str, subject: str, body: str):
    ...
```

Воркер запускается как обычно:

```bash
celery -A Services.tasks:app worker --loglevel=info
```

## Постановка в очередь из обработчика

```python
from Services.tasks import send_email

async def handler(request):                # Api/v1/Signup/Post.py
    data = await request.json()
    send_email.delay(data["email"], "Welcome", "Thanks for signing up!")
    return Response.json({"queued": True}, status=202)
```

## Фоновые задачи vs Celery

| Задача | Инструмент |
|------|-----|
| Fire-and-forget работа, привязанная к одному ответу, best-effort | [Response background](../guide/background-lifecycle.md) |
| Долговечная, с ретраями, распределённая работа | **Celery** |

Только фабрика, без расширения:

```python
from endocore.extensions import celery_app
app = celery_app("myapp", broker="redis://localhost:6379/1")
```
