"""Encrypted FileField: many payloads roundtrip; leak/tamper always fail."""

from __future__ import annotations

import pytest

from endocore.orm import (
    Model, fields, configure, create_all, configure_storage, generate_key,
    EncryptedFileSystemStorage, StorageError,
)
from endocore.orm.connection import get_connection


class Doc(Model):
    blob = fields.FileField(upload_to="d")


@pytest.fixture()
def db(tmp_path):
    configure(backend="sqlite", database=":memory:")
    configure_storage(root=tmp_path / "store", key=generate_key())
    create_all(Doc)
    yield
    get_connection().close()


PAYLOADS = [
    b"", b"a", b"\x00\x01\x02", b"hello world", b"X" * 10000,
    bytes(range(256)), "unicode héllo".encode(), b"\n\r\t",
] + [f"payload-{i}".encode() for i in range(40)]


@pytest.mark.parametrize("payload", PAYLOADS)
def test_roundtrip(db, payload):
    d = Doc.objects.create(blob=payload)
    assert Doc.objects.get(pk=d.pk).blob.read() == payload


@pytest.mark.parametrize("payload", PAYLOADS[:20])
def test_plaintext_not_on_disk(db, payload):
    if len(payload) < 4:
        pytest.skip("too short to look for")
    d = Doc.objects.create(blob=payload)
    on_disk = d.blob.storage.path(d.blob.name).read_bytes()
    assert payload not in on_disk
    assert on_disk[:4] == b"ENC1"


@pytest.mark.parametrize("payload", PAYLOADS[:20])
def test_leak_without_key_unrecoverable(db, payload):
    d = Doc.objects.create(blob=payload)
    attacker = EncryptedFileSystemStorage(root=d.blob.storage.root, key=generate_key())
    with pytest.raises(StorageError):
        attacker.open(d.blob.name)


@pytest.mark.parametrize("payload", PAYLOADS[:15])
def test_tamper_detected(db, payload):
    if not payload:
        pytest.skip("empty")
    d = Doc.objects.create(blob=payload)
    path = d.blob.storage.path(d.blob.name)
    raw = bytearray(path.read_bytes())
    raw[-1] ^= 0x01
    path.write_bytes(raw)
    with pytest.raises(StorageError):
        Doc.objects.get(pk=d.pk).blob.read()


@pytest.mark.parametrize("bad", ["../escape", "../../etc", "a/../../b"])
def test_path_traversal_refused(db, bad):
    from endocore.orm.storage import get_storage

    with pytest.raises(StorageError):
        get_storage().save(bad, b"x")


@pytest.mark.parametrize("_", list(range(20)))
def test_random_filenames_unique(db, _):
    a = Doc.objects.create(blob=b"same")
    b = Doc.objects.create(blob=b"same")
    assert a.blob.name != b.blob.name  # random names even for identical content


@pytest.mark.parametrize("keylen", [16, 24, 31, 33, 64])
def test_wrong_key_length_rejected(keylen):
    from endocore.orm.exceptions import ConfigurationError

    with pytest.raises(ConfigurationError):
        EncryptedFileSystemStorage(root=".", key=b"x" * keylen)
