"""Encrypted FileField — the whole point is that a leak is unrecoverable."""

from __future__ import annotations

import pytest

from endocore.orm import (
    Model, fields, configure, create_all, configure_storage, generate_key,
    EncryptedFileSystemStorage, StorageError,
)
from endocore.orm.connection import get_connection


class Doc(Model):
    title = fields.CharField(max_length=50)
    blob = fields.FileField(upload_to="secret/docs")


@pytest.fixture()
def db(tmp_path):
    configure(backend="sqlite", database=":memory:")
    # An arbitrary nested folder — files can live anywhere the user wants.
    configure_storage(root=tmp_path / "any" / "where", key=generate_key())
    create_all(Doc)
    yield
    get_connection().close()


SECRET = b"TOP SECRET \x00\x01 " + b"A" * 200


def test_roundtrip(db):
    d = Doc.objects.create(title="r", blob=SECRET)
    assert Doc.objects.get(pk=d.pk).blob.read() == SECRET


def test_db_stores_only_opaque_key(db):
    d = Doc.objects.create(title="r", blob=SECRET)
    key = Doc.objects.values_list("blob", flat=True).first()
    assert key.startswith("secret/docs/") and key.endswith(".enc")


def test_plaintext_never_on_disk(db):
    d = Doc.objects.create(title="r", blob=SECRET)
    on_disk = d.blob.storage.path(d.blob.name).read_bytes()
    assert SECRET not in on_disk
    assert on_disk[:4] == b"ENC1"


def test_leak_without_key_is_unrecoverable(db):
    d = Doc.objects.create(title="r", blob=SECRET)
    # Attacker copies the storage folder but has a different key.
    attacker = EncryptedFileSystemStorage(root=d.blob.storage.root, key=generate_key())
    with pytest.raises(StorageError):
        attacker.open(d.blob.name)


def test_tamper_is_detected(db):
    d = Doc.objects.create(title="r", blob=SECRET)
    path = d.blob.storage.path(d.blob.name)
    raw = bytearray(path.read_bytes())
    raw[-1] ^= 0x01  # flip one ciphertext bit
    path.write_bytes(raw)
    with pytest.raises(StorageError):
        Doc.objects.get(pk=d.pk).blob.read()


def test_delete_removes_file(db):
    d = Doc.objects.create(title="r", blob=SECRET)
    name = d.blob.name
    storage = d.blob.storage
    assert storage.exists(name)
    d.blob.delete()
    assert not storage.exists(name)


def test_missing_key_fails_closed(tmp_path, monkeypatch):
    monkeypatch.delenv("ENDOCORE_FILE_KEY", raising=False)
    from endocore.orm.exceptions import ConfigurationError

    with pytest.raises(ConfigurationError):
        configure_storage(root=tmp_path, key=None)


def test_path_traversal_refused(db):
    storage = get_connection() and None  # noqa - just for readability
    from endocore.orm.storage import get_storage

    with pytest.raises(StorageError):
        get_storage().save("../escape", b"x")
