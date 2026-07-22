# Email

Крошечный SMTP-клиент на стандартной библиотеке — **без дополнительных
зависимостей**.

## Регистрация

```python
# extensions.py
from endocore.extensions import EmailExtension

extensions = [
    EmailExtension(
        host="smtp.example.com", port=587, use_tls=True,
        username="apikey", password="…", default_from="no-reply@example.com",
    ),
]
```

Это регистрирует `EmailClient` как DI-провайдер под именем `email` (и по типу).

## Отправка из обработчика

```python
async def handler(request, email):         # инжектированный EmailClient
    email.send(
        to="user@example.com",
        subject="Welcome",
        body="Thanks for signing up!",
    )
    return Response.json({"sent": True})
```

## HTML и несколько получателей

```python
email.send(
    to=["a@example.com", "b@example.com"],
    subject="Report",
    body="<h1>Weekly report</h1>…",
    html=True,
    from_addr="reports@example.com",
)
```

## Без расширения

```python
from endocore.extensions import EmailClient

client = EmailClient(host="localhost", port=25)
client.send(to="a@b.com", subject="Hi", body="Hello")
```

!!! tip "Отправка в фоне"
    Отправка почты бывает медленной — верните её как
    [фоновую задачу](../guide/background-lifecycle.md), чтобы клиент не ждал,
    либо поставьте в очередь через [Celery](celery.md) ради ретраев.
