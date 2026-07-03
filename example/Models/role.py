"""Role model."""

from dataclasses import dataclass


@dataclass
class Role:
    name: str
    created: bool = False
