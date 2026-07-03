"""Service integration extensions (wiring, lazy deps, lifecycle)."""

from __future__ import annotations

import pytest

from endocore.extensions import (
    CacheExtension, CeleryExtension, EmailClient, EmailExtension, Extension, RedisExtension,
)


class FakeApp:
    def __init__(self):
        self.providers_by_name = {}
        self.providers_by_type = {}

    def provide(self, key, factory, *, singleton=True):
        if isinstance(key, type):
            self.providers_by_type[key] = factory
        else:
            self.providers_by_name[key] = factory


def test_base_extension_noop():
    ext = Extension()
    app = FakeApp()
    ext.setup(app)  # no error
    assert app.providers_by_name == {}


def test_cache_extension_registers():
    app = FakeApp()
    CacheExtension(backend="memory").setup(app)
    assert "cache" in app.providers_by_name


def test_cache_extension_custom_name():
    app = FakeApp()
    CacheExtension(backend="memory", name="mycache").setup(app)
    assert "mycache" in app.providers_by_name


def test_email_extension_registers():
    app = FakeApp()
    EmailExtension(host="localhost").setup(app)
    assert "email" in app.providers_by_name
    assert EmailClient in app.providers_by_type


def test_email_client_builds_message():
    client = EmailClient(host="localhost", default_from="from@x.com")
    msg = client._build(["a@b.com", "c@d.com"], "Subj", "Body")
    assert msg["To"] == "a@b.com, c@d.com"
    assert msg["From"] == "from@x.com"
    assert msg["Subject"] == "Subj"


def test_email_client_html():
    client = EmailClient(host="localhost")
    msg = client._build("a@b.com", "S", "<b>hi</b>", html=True)
    assert msg.is_multipart()


def test_redis_extension_registers_provider():
    app = FakeApp()
    fake_client = object()
    ext = RedisExtension(client=fake_client)
    ext.setup(app)
    assert "redis" in app.providers_by_name
    assert app.providers_by_name["redis"]() is fake_client


def test_celery_extension_registers_provider():
    app = FakeApp()
    fake = object()
    ext = CeleryExtension(app=fake)
    ext.setup(app)
    assert "celery" in app.providers_by_name
    assert app.providers_by_name["celery"]() is fake


def test_redis_missing_dep_message():
    from endocore.extensions.redis import redis_client

    try:
        import redis  # noqa: F401
        pytest.skip("redis installed")
    except ImportError:
        with pytest.raises(ImportError, match="redis"):
            redis_client()


def test_celery_missing_dep_message():
    from endocore.extensions.celery import celery_app

    try:
        import celery  # noqa: F401
        pytest.skip("celery installed")
    except ImportError:
        with pytest.raises(ImportError, match="celery"):
            celery_app()
