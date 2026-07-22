"""Client-generated primary keys (UUIDField with a default) work with save().

Regression: save() used "pk is None" to pick INSERT vs UPDATE, so a model
whose pk default filled it before the first save was UPDATEd (0 rows) and
auto_now_add never ran.
"""

import uuid

import pytest

from endocore.orm import Model, fields, configure, create_all


class Account(Model):
    class Meta:
        table = "uuidpk_accounts"

    id      = fields.UUIDField(primary_key=True, default=uuid.uuid4)
    name    = fields.CharField(max_length=50, unique=True)
    created = fields.DateTimeField(auto_now_add=True)


@pytest.fixture(autouse=True)
def _db():
    configure(backend="sqlite", database=":memory:")
    create_all(Account)
    yield


def test_create_inserts_with_preset_uuid_pk():
    acc = Account.objects.create(name="ada")
    assert isinstance(acc.id, uuid.UUID)
    assert acc.created is not None
    assert Account.objects.count() == 1
    assert Account.objects.get(name="ada").id == acc.id


def test_fetched_instance_saves_as_update():
    acc = Account.objects.create(name="ada")
    fetched = Account.objects.get(pk=acc.id)
    fetched.name = "lovelace"
    fetched.save()
    assert Account.objects.count() == 1
    assert Account.objects.get(pk=acc.id).name == "lovelace"


def test_created_instance_resaves_as_update():
    acc = Account.objects.create(name="ada")
    acc.name = "lovelace"
    acc.save()
    assert Account.objects.count() == 1


def test_update_or_create_with_uuid_pk():
    Account.objects.create(name="ada")
    obj, created = Account.objects.update_or_create(name="ada", defaults={})
    assert not created
    assert Account.objects.count() == 1
    obj2, created2 = Account.objects.update_or_create(name="bo", defaults={})
    assert created2
    assert Account.objects.count() == 2


def test_delete_then_save_reinserts():
    acc = Account.objects.create(name="ada")
    acc_id = acc.id
    acc.delete()
    assert Account.objects.count() == 0
    acc.id = acc_id
    acc.save()
    assert Account.objects.count() == 1


def test_refresh_from_db_keeps_update_semantics():
    acc = Account.objects.create(name="ada")
    acc.refresh_from_db()
    acc.name = "lovelace"
    acc.save()
    assert Account.objects.count() == 1
