# Celery

Offload slow or reliable background work to a Celery task queue.

```bash
pip install "endocore[celery]"     # plus a broker, e.g. Redis or RabbitMQ
```

## Register the Celery app

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

This registers the Celery app as a DI provider under the name `celery`.

## Define tasks

```python
# Services/tasks.py
from endocore.extensions import celery_app

app = celery_app("myapp", broker="redis://localhost:6379/1")

@app.task
def send_email(to: str, subject: str, body: str):
    ...
```

Run a worker as usual:

```bash
celery -A Services.tasks:app worker --loglevel=info
```

## Enqueue from a handler

```python
from Services.tasks import send_email

async def handler(request):                # Api/v1/Signup/Post.py
    data = await request.json()
    send_email.delay(data["email"], "Welcome", "Thanks for signing up!")
    return Response.json({"queued": True}, status=202)
```

## Background tasks vs Celery

| Need | Use |
|------|-----|
| Fire-and-forget work tied to one response, best-effort | [Response background](../guide/background-lifecycle.md) |
| Durable, retried, distributed work | **Celery** |

Just the factory, without the extension:

```python
from endocore.extensions import celery_app
app = celery_app("myapp", broker="redis://localhost:6379/1")
```
