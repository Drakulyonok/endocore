# Shop — coins, purchases and payment-gateway webhooks on EndoCore

The production-hardening demo: every money operation is race-proof and
idempotent, and the whole test suite runs against **real PostgreSQL with
`pool_size=5`** when a DSN is provided.

```
end dev                          # from this directory; DB auto-created on startup
python -m pytest Tests           # SQLite (default)

# the same suite — races included — against a real Postgres pool:
$env:ENDOCORE_TEST_POSTGRES_DSN = "postgresql://user:pass@localhost:5432/endocore_test"
python -m pytest Tests
```

## Money-safety invariants

| Threat | Defense | Proven by |
|--------|---------|-----------|
| Overdraft under concurrent purchases | conditional `UPDATE … WHERE balance >= cost` (`F()` expression) — never check-then-write | `test_race.py`: 8 racers, 100 coins, price 30 → exactly 3×201, 5×402, balance 10 |
| Double charge on client/proxy retry | `Idempotency-Key` claim (UNIQUE) → process → stored response replayed with `Idempotent-Replay: true` | `test_idempotency.py`: sequential + 6-way concurrent same-key races |
| Double credit on gateway webhook retry | `Payment.external_id` UNIQUE + credit in the same transaction; duplicates answer 200 `{"duplicate": true}` | 3× sequential + 6-way concurrent webhook retries |

Framework-level pool races live in `tests/orm/test_postgres_pool.py`
(same DSN gate): simultaneous open transactions, no-overdraft spends, and
UNIQUE races that must not poison the pool.

## API (v1)

| Method | Path | Notes |
|--------|------|-------|
| POST | `/v1/auth/register` / `login` / `logout` | account + wallet created atomically |
| GET | `/v1/wallet` | coin balance |
| GET/POST | `/v1/products` | catalogue |
| POST | `/v1/buy` | requires `Idempotency-Key` header (1..128 chars) |
| GET | `/v1/purchases` | purchase history |
| POST | `/v1/webhook/payment` | gateway callback; `X-Webhook-Secret` header |

Notes for production: idempotency records claimed but never finished (a crash
mid-request) stay in status 0 and answer 409 — sweep records older than some
TTL with a background job. Config via env: `SHOP_SECRET`, `SHOP_DB`,
`SHOP_WEBHOOK_SECRET`.
