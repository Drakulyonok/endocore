# Email

A tiny SMTP email client built on the standard library — **no extra
dependency**.

## Register it

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

This registers an `EmailClient` as a DI provider under the name `email` (and by
type).

## Send from a handler

```python
async def handler(request, email):         # injected EmailClient
    email.send(
        to="user@example.com",
        subject="Welcome",
        body="Thanks for signing up!",
    )
    return Response.json({"sent": True})
```

## HTML and multiple recipients

```python
email.send(
    to=["a@example.com", "b@example.com"],
    subject="Report",
    body="<h1>Weekly report</h1>…",
    html=True,
    from_addr="reports@example.com",
)
```

## Without the extension

```python
from endocore.extensions import EmailClient

client = EmailClient(host="localhost", port=25)
client.send(to="a@b.com", subject="Hi", body="Hello")
```

!!! tip "Sending in the background"
    Sending email can be slow — return it as a
    [background task](../guide/background-lifecycle.md) so the client isn't kept
    waiting, or enqueue it via [Celery](celery.md) for retries.
