"""Local (versioned) service: role creation business logic.

Lives under Api/v1/.../Services/ so it is copied when `endo version create` makes
a new version — v2 can diverge without touching v1.
"""

from Api.v1.User.Services.validate_role import validate_role


def create_role(payload: dict) -> dict:
    validate_role(payload)
    return {"name": payload["name"], "created": True}
