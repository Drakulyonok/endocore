"""Email integration over stdlib ``smtplib`` (no extra dependency)."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from endocore.extensions import Extension


class EmailClient:
    """A tiny SMTP email sender."""

    def __init__(self, host: str = "localhost", port: int = 25, *, username: str | None = None,
                 password: str | None = None, use_tls: bool = False, default_from: str | None = None) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.default_from = default_from

    def _build(self, to, subject, body, *, from_addr=None, html=False) -> EmailMessage:
        message = EmailMessage()
        message["From"] = from_addr or self.default_from or (self.username or "no-reply@localhost")
        message["To"] = ", ".join(to) if isinstance(to, (list, tuple)) else to
        message["Subject"] = subject
        if html:
            message.set_content("This message requires an HTML-capable client.")
            message.add_alternative(body, subtype="html")
        else:
            message.set_content(body)
        return message

    def send(self, to, subject: str, body: str, *, from_addr: str | None = None, html: bool = False) -> None:
        message = self._build(to, subject, body, from_addr=from_addr, html=html)
        with smtplib.SMTP(self.host, self.port) as server:
            if self.use_tls:
                server.starttls()
            if self.username:
                server.login(self.username, self.password or "")
            server.send_message(message)


class EmailExtension(Extension):
    """Registers an :class:`EmailClient` as a DI provider under ``name`` ('email')."""

    name = "email"

    def __init__(self, *, name: str = "email", **kwargs) -> None:
        self.name = name
        self.client = EmailClient(**kwargs)

    def setup(self, app) -> None:
        app.provide(self.name, lambda: self.client, singleton=True)
        app.provide(EmailClient, lambda: self.client, singleton=True)
