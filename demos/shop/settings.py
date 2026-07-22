"""Shop demo settings — everything overridable via environment."""

from endocore import env

SECRET = env("SHOP_SECRET", "dev-secret-change-me")
DATABASE = env("SHOP_DB", "shop.db")
#: shared secret the payment gateway signs webhooks with (demo-simplified)
WEBHOOK_SECRET = env("SHOP_WEBHOOK_SECRET", "dev-webhook-secret")
