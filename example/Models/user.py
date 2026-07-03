"""User model — plain dataclass for the MVP (pydantic is post-MVP)."""

from dataclasses import dataclass


@dataclass
class User:
    id: str
    name: str
    email: str | None = None
