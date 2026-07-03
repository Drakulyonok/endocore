"""Local (versioned) service: role payload validation."""


def validate_role(payload: dict) -> None:
    if not payload or not payload.get("name"):
        raise ValueError("role 'name' is required")
