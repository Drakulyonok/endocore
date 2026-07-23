"""User-written test (the framework never generates these).

Run with `endo test` or `pytest` from the example/ directory.
"""

import pytest

from Api.v1.User.Services.create_role import create_role
from Api.v1.User.Services.validate_role import validate_role


def test_create_role_ok():
    result = create_role({"name": "admin"})
    assert result == {"name": "admin", "created": True}


def test_validate_role_requires_name():
    with pytest.raises(ValueError):
        validate_role({})
