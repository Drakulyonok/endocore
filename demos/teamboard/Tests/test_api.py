"""REST flow: auth, boards, membership, cards, permissions."""

from __future__ import annotations

import asyncio

from Tests.conftest import acall, register, session_of


def run(coro):
    return asyncio.run(coro)


def test_register_login_me(app):
    async def scenario():
        cookie = await register(app, "ada@example.com", "Ada")
        status, me, _ = await acall(app, "GET", "/v1/me", cookie=cookie)
        assert status == 200 and me["email"] == "ada@example.com"

        status, _, _ = await acall(app, "POST", "/v1/auth/register",
                                   body={"email": "ada@example.com", "name": "Dup",
                                         "password": "password123"})
        assert status == 409

        status, _, headers = await acall(app, "POST", "/v1/auth/login",
                                         body={"email": "ada@example.com",
                                               "password": "password123"})
        assert status == 200
        relogin = session_of(headers)
        status, me, _ = await acall(app, "GET", "/v1/me", cookie=relogin)
        assert status == 200 and me["name"] == "Ada"

        status, _, _ = await acall(app, "POST", "/v1/auth/login",
                                   body={"email": "ada@example.com", "password": "wrong"})
        assert status == 401

    run(scenario())


def test_anonymous_is_rejected(app):
    async def scenario():
        for method, path in [("GET", "/v1/me"), ("GET", "/v1/boards"),
                             ("POST", "/v1/boards")]:
            status, _, _ = await acall(app, method, path, body={})
            assert status == 401, (method, path, status)

    run(scenario())


def test_board_and_card_lifecycle(app):
    async def scenario():
        cookie = await register(app, "ada@example.com", "Ada")

        status, board, _ = await acall(app, "POST", "/v1/boards",
                                       body={"title": "Sprint 1"}, cookie=cookie)
        assert status == 201 and board["title"] == "Sprint 1"
        board_id = board["id"]

        status, listing, _ = await acall(app, "GET", "/v1/boards", cookie=cookie)
        assert [b["id"] for b in listing["boards"]] == [board_id]

        status, card, _ = await acall(
            app, "POST", f"/v1/boards/{board_id}/cards",
            body={"title": "Write tests", "status": "todo"}, cookie=cookie)
        assert status == 201
        card_id = card["id"]

        status, card, _ = await acall(app, "PATCH", f"/v1/cards/{card_id}",
                                      body={"status": "doing", "position": 3},
                                      cookie=cookie)
        assert status == 200 and card["status"] == "doing" and card["position"] == 3

        status, detail, _ = await acall(app, "GET", f"/v1/boards/{board_id}", cookie=cookie)
        assert status == 200 and len(detail["cards"]) == 1

        status, _, _ = await acall(app, "DELETE", f"/v1/cards/{card_id}", cookie=cookie)
        assert status == 204
        status, detail, _ = await acall(app, "GET", f"/v1/boards/{board_id}", cookie=cookie)
        assert detail["cards"] == []

    run(scenario())


def test_membership_and_permissions(app):
    async def scenario():
        ada = await register(app, "ada@example.com", "Ada")
        bob = await register(app, "bob@example.com", "Bob")

        _, board, _ = await acall(app, "POST", "/v1/boards",
                                  body={"title": "Private"}, cookie=ada)
        board_id = board["id"]

        # A stranger sees nothing and can do nothing.
        status, _, _ = await acall(app, "GET", f"/v1/boards/{board_id}", cookie=bob)
        assert status == 403
        status, _, _ = await acall(app, "PATCH", f"/v1/boards/{board_id}",
                                   body={"title": "hack"}, cookie=bob)
        assert status == 403

        # Invited -> can view and add cards, still can't rename (owner only).
        status, _, _ = await acall(app, "POST", f"/v1/boards/{board_id}/members",
                                   body={"email": "bob@example.com"}, cookie=ada)
        assert status == 201
        status, _, _ = await acall(app, "GET", f"/v1/boards/{board_id}", cookie=bob)
        assert status == 200
        status, _, _ = await acall(app, "POST", f"/v1/boards/{board_id}/cards",
                                   body={"title": "From Bob"}, cookie=bob)
        assert status == 201
        status, _, _ = await acall(app, "PATCH", f"/v1/boards/{board_id}",
                                   body={"title": "hack"}, cookie=bob)
        assert status == 403

        # Double invite -> 409; unknown email -> 404.
        status, _, _ = await acall(app, "POST", f"/v1/boards/{board_id}/members",
                                   body={"email": "bob@example.com"}, cookie=ada)
        assert status == 409
        status, _, _ = await acall(app, "POST", f"/v1/boards/{board_id}/members",
                                   body={"email": "ghost@example.com"}, cookie=ada)
        assert status == 404

    run(scenario())


def test_validation_errors(app):
    async def scenario():
        cookie = await register(app, "ada@example.com", "Ada")
        status, _, _ = await acall(app, "POST", "/v1/boards", body={"title": "  "},
                                   cookie=cookie)
        assert status == 422
        status, _, _ = await acall(app, "POST", "/v1/auth/register",
                                   body={"email": "bad", "name": "x", "password": "short"})
        assert status == 422
        status, _, _ = await acall(app, "GET", "/v1/boards/999999", cookie=cookie)
        assert status == 404

    run(scenario())
