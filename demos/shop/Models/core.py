"""Shop data model.

Money-safety invariants live in the schema, not in handler code:
- ``Payment.external_id`` UNIQUE — a retried gateway webhook can never credit
  the wallet twice (insert + credit share one transaction).
- ``IdempotencyRecord.key`` UNIQUE — a retried purchase request can never
  charge twice; the stored response is replayed instead.
- Spends are conditional UPDATEs (``balance >= cost``) — no overdraft under
  any concurrency, on SQLite or PostgreSQL.
"""

from endocore.orm import Model, configure, fields

from settings import DATABASE

configure(backend="sqlite", database=DATABASE)


class User(Model):
    class Meta:
        table = "shop_users"

    email = fields.CharField(max_length=120, unique=True)
    name = fields.CharField(max_length=80)
    password_hash = fields.CharField(max_length=200)
    created = fields.DateTimeField(auto_now_add=True)


class Wallet(Model):
    class Meta:
        table = "shop_wallets"

    user = fields.OneToOneField(User, on_delete="CASCADE")
    balance = fields.IntegerField(default=0)  # coins, integer only


class Product(Model):
    class Meta:
        table = "shop_products"
        ordering = ["id"]

    name = fields.CharField(max_length=120, unique=True)
    price = fields.IntegerField()


class Purchase(Model):
    class Meta:
        table = "shop_purchases"
        ordering = ["-id"]

    user = fields.ForeignKey(User, on_delete="CASCADE")
    product = fields.ForeignKey(Product, on_delete="CASCADE")
    price = fields.IntegerField()  # price at purchase time
    created = fields.DateTimeField(auto_now_add=True)


class IdempotencyRecord(Model):
    """One client request key -> one processed result (replayed on retries)."""

    class Meta:
        table = "shop_idempotency"

    key = fields.CharField(max_length=128, unique=True)
    user = fields.ForeignKey(User, on_delete="CASCADE")
    status_code = fields.IntegerField(default=0)  # 0 = claimed, still processing
    body = fields.TextField(default="")
    created = fields.DateTimeField(auto_now_add=True)


class Payment(Model):
    """A credit from the payment gateway; external_id makes retries no-ops."""

    class Meta:
        table = "shop_payments"

    external_id = fields.CharField(max_length=128, unique=True)
    user = fields.ForeignKey(User, on_delete="CASCADE")
    amount = fields.IntegerField()
    created = fields.DateTimeField(auto_now_add=True)


ALL_MODELS = (User, Wallet, Product, Purchase, IdempotencyRecord, Payment)
