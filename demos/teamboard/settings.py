"""TeamBoard settings — everything overridable via environment."""

from endocore import env

SECRET = env("TEAMBOARD_SECRET", "dev-secret-change-me")
DATABASE = env("TEAMBOARD_DB", "teamboard.db")
