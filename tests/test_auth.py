"""Built-in auth: password hashing, timing-attack resistance, cookie sessions,
and the full login -> me -> logout flow with the DI guard."""

from __future__ import annotations

import re
import time

import pytest

from endocore import hash_password, needs_rehash, verify_password
from endocore.core.application import Application
from endocore.middleware.sessions import Session, session_middleware
from tests.conftest import call

SECRET = "test-secret-key"


# -- password hashing --------------------------------------------------------

def test_hash_and_verify_roundtrip():
    encoded = hash_password("s3cret-пароль")
    assert encoded.startswith("scrypt$")
    assert verify_password("s3cret-пароль", encoded)
    assert not verify_password("wrong", encoded)


def test_salts_are_unique():
    assert hash_password("same") != hash_password("same")


def test_verify_rejects_garbage_without_raising():
    assert not verify_password("x", "")
    assert not verify_password("x", "not-a-hash")
    assert not verify_password("x", "md5$1$2$3$AAAA$BBBB")


def test_empty_password_rejected():
    with pytest.raises(ValueError):
        hash_password("")


def test_needs_rehash():
    assert not needs_rehash(hash_password("x"))
    assert needs_rehash("scrypt$4096$8$1$AAAA$BBBB")  # below current N
    assert needs_rehash("bcrypt$whatever")
    assert needs_rehash("garbage")


# -- timing-attack resistance ------------------------------------------------

def _best_time(fn, runs: int = 3) -> float:
    """Fastest of ``runs`` calls — the min is the least noisy point estimate."""
    best = float("inf")
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return best


def test_digest_comparison_is_constant_time(monkeypatch):
    """The digest check must go through hmac.compare_digest, never ``==``."""
    import endocore.core.passwords as passwords

    calls: list[tuple[bytes, bytes]] = []
    real = passwords.hmac.compare_digest

    def spy(a, b):
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr(passwords.hmac, "compare_digest", spy)
    encoded = hash_password("pw")
    assert verify_password("pw", encoded)
    assert not verify_password("nope", encoded)
    assert len(calls) == 2


def test_wrong_password_burns_full_derivation():
    """A rejection must cost a full scrypt run — a short-circuit would show up
    as ~0 against scrypt's tens of milliseconds."""
    encoded = hash_password("correct horse battery staple")
    t_right = _best_time(lambda: verify_password("correct horse battery staple", encoded))
    t_wrong = _best_time(lambda: verify_password("hunter2", encoded))
    assert t_wrong > t_right * 0.5


def test_unknown_user_is_not_enumerable_by_timing():
    """verify_password(pw, None) — the 'no such account' login path — must
    cost a full scrypt run too, so response timing can't enumerate emails."""
    encoded = hash_password("real-users-password")
    t_known = _best_time(lambda: verify_password("attempt", encoded))
    t_unknown = _best_time(lambda: verify_password("attempt", None))
    assert not verify_password("attempt", None)
    assert t_unknown > t_known * 0.5


# -- Session dict ------------------------------------------------------------

def test_reads_do_not_mark_modified():
    session = Session({"a": 1})
    assert session["a"] == 1
    assert not session.modified


def test_writes_mark_modified():
    session = Session()
    session["b"] = 2
    assert session.modified


def test_setdefault_marks_only_on_insert():
    fresh = Session()
    fresh.setdefault("k", "v")
    assert fresh.modified

    existing = Session({"k": "v"})
    existing.setdefault("k", "other")
    assert not existing.modified


def test_clear_marks_modified():
    session = Session({"x": 1})
    session.clear()
    assert session.modified and not session


# -- end-to-end: login -> me -> logout ---------------------------------------

@pytest.fixture()
def auth_app(tmp_path):
    def write(rel, body):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    write("Middleware/__init__.py", (
        "from endocore.middleware import session_middleware\n"
        f"middlewares = [session_middleware(secret={SECRET!r})]\n"
    ))
    write("Api/v1/Login/Post.py", (
        "from endocore import Response, login\n"
        "async def handler(request):\n"
        "    body = await request.json()\n"
        "    login(request, body['user_id'])\n"
        "    return Response.json({'ok': True})\n"
    ))
    write("Api/v1/Logout/Post.py", (
        "from endocore import Response, logout\n"
        "async def handler(request):\n"
        "    logout(request)\n"
        "    return Response.json({'ok': True})\n"
    ))
    write("Api/v1/Me/Get.py", (
        "from endocore import Depends, Response, require_user_id\n"
        "async def handler(request, user_id = Depends(require_user_id)):\n"
        "    return Response.json({'user_id': user_id})\n"
    ))
    return Application(app_dir=tmp_path)


def _session_cookie(headers: dict[str, str]) -> str | None:
    match = re.match(r"session=([^;]*)", headers.get("set-cookie", ""))
    return match.group(1) if match else None


def _get_me(app, cookie: str | None = None):
    headers = [(b"cookie", f"session={cookie}".encode())] if cookie else []
    return call(app, "GET", "/v1/me", headers=headers)


def test_anonymous_gets_401(auth_app):
    status, _, _ = _get_me(auth_app)
    assert status == 401


def test_login_me_logout_flow(auth_app):
    status, _, headers = call(auth_app, "POST", "/v1/login", body=b'{"user_id": 42}')
    assert status == 200
    cookie = _session_cookie(headers)
    assert cookie
    assert "HttpOnly" in headers["set-cookie"]

    status, body, _ = _get_me(auth_app, cookie)
    assert status == 200
    assert b'"user_id": 42' in body

    status, _, headers = call(
        auth_app, "POST", "/v1/logout",
        headers=[(b"cookie", f"session={cookie}".encode())],
    )
    assert status == 200
    assert "Max-Age=0" in headers["set-cookie"]

    status, _, _ = _get_me(auth_app)
    assert status == 401


def test_tampered_cookie_is_anonymous(auth_app):
    _, _, headers = call(auth_app, "POST", "/v1/login", body=b'{"user_id": 42}')
    cookie = _session_cookie(headers)
    forged = cookie[:-4] + ("AAAA" if not cookie.endswith("AAAA") else "BBBB")
    status, _, _ = _get_me(auth_app, forged)
    assert status == 401


def test_unmodified_session_sets_no_cookie(auth_app):
    status, _, headers = _get_me(auth_app)
    assert status == 401
    assert "set-cookie" not in headers


def test_auth_without_session_middleware_is_loud():
    from endocore import login
    from endocore.core.exceptions import EndoCoreError

    class FakeRequest:
        pass

    with pytest.raises(EndoCoreError, match="session_middleware"):
        login(FakeRequest(), 1)
