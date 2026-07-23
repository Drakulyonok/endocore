# TeamBoard — kanban demo on EndoCore

A real-world exercise of the framework: sessions + scrypt auth, FK relations
with access control, async ORM + `aatomic()`, and **live board updates over
WebSocket** (REST mutations broadcast to every subscribed member).

```
endo dev                          # from this directory; DB auto-created on startup
python -m pytest Tests           # e2e suite (REST + live WebSocket)
```

## API (v1)

| Method | Path | Notes |
|--------|------|-------|
| POST | `/v1/auth/register` | email + name + password (8+) → logs in |
| POST | `/v1/auth/login` | enumeration-safe (`verify_password(..., None)`) |
| POST | `/v1/auth/logout` | |
| GET | `/v1/me` | 401 for anonymous (DI: `require_user_id`) |
| GET/POST | `/v1/boards` | your boards / create (owner = member) |
| GET/PATCH/DELETE | `/v1/boards/{id}` | detail with cards / rename / delete (owner) |
| POST | `/v1/boards/{id}/members` | invite by email (owner) |
| POST | `/v1/boards/{id}/cards` | create card → `card.created` broadcast |
| PATCH/DELETE | `/v1/cards/{id}` | edit/move/delete → live broadcast |
| WS | `/v1/boards/{id}` | live events; session cookie auth + membership check |

Events: `card.created` / `card.updated` / `card.deleted` / `board.renamed` /
`board.deleted`, each with the serialized payload.

Config via env: `TEAMBOARD_SECRET`, `TEAMBOARD_DB`.
