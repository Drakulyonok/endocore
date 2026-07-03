"""GLOBAL service — shared across all versions, never copied on version create."""


def authenticate(token: str | None) -> dict | None:
    if not token:
        return None
    # Demo stub; real logic would verify a signature / look up a session.
    return {"token": token, "user_id": "demo"}
