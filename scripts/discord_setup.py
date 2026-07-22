"""One-shot Discord server provisioner for the EndoCore community.

Creates the standard category/channel/role layout for an open-source project
server, then the bot's job is done — kick it or leave it, your call. Stdlib
only (``urllib``), matching the framework's own minimal-dependency ethos.

Setup (Discord Developer Portal, https://discord.com/developers/applications):
    1. New Application -> name it "EndoCore Setup" (or anything).
    2. Bot tab -> "Add Bot" -> "Reset Token" -> copy it. Keep it secret; it
       grants full control of any server the bot joins.
    3. OAuth2 -> URL Generator -> scopes: "bot" -> permissions: "Administrator"
       (simplest for a one-off setup run) -> copy the generated URL.
    4. Create your Discord server (if you haven't), open the URL from step 3
       in a browser, pick that server, authorize.
    5. Enable Developer Mode in Discord (User Settings -> Advanced), then
       right-click the server icon -> "Copy Server ID" -> that's your guild id.

Run:
    DISCORD_BOT_TOKEN=... DISCORD_GUILD_ID=... python scripts/discord_setup.py

Re-running is safe: everything is looked up by name first and only created
if missing, so a second run just confirms the layout and does nothing.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://discord.com/api/v10"

# Discord channel "type" values (https://discord.com/developers/docs/resources/channel).
TEXT, VOICE, CATEGORY = 0, 2, 4

# Permission bit needed to deny @everyone posting in read-only channels.
SEND_MESSAGES = 1 << 11


def _request(token: str, method: str, path: str, body: dict | None = None):
    url = f"{API}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bot {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "EndoCoreSetupBot (https://github.com/Drakulyonok/endocore, 1.0)")

    while True:
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            if exc.code == 429:  # rate limited — back off and retry
                payload = json.loads(exc.read() or b"{}")
                time.sleep(float(payload.get("retry_after", 1)) + 0.1)
                continue
            detail = exc.read().decode("utf-8", "replace")
            raise SystemExit(f"Discord API error {exc.code} on {method} {path}: {detail}") from None


def ensure_role(token: str, guild_id: str, existing: list[dict], name: str, **fields) -> str:
    for role in existing:
        if role["name"] == name:
            print(f"  role  {name!r} already exists")
            return role["id"]
    role = _request(token, "POST", f"/guilds/{guild_id}/roles", {"name": name, **fields})
    print(f"  role  {name!r} created")
    return role["id"]


def ensure_category(token: str, guild_id: str, existing: list[dict], name: str, position: int) -> str:
    for ch in existing:
        if ch["type"] == CATEGORY and ch["name"] == name:
            print(f"category {name!r} already exists")
            return ch["id"]
    ch = _request(
        token, "POST", f"/guilds/{guild_id}/channels",
        {"name": name, "type": CATEGORY, "position": position},
    )
    existing.append(ch)
    print(f"category {name!r} created")
    return ch["id"]


def ensure_channel(
    token: str, guild_id: str, existing: list[dict], name: str, *, kind: int,
    parent_id: str, topic: str = "", read_only_for_everyone: bool = False,
) -> str:
    for ch in existing:
        if ch["type"] == kind and ch["name"] == name and ch.get("parent_id") == parent_id:
            print(f"  #{name} already exists")
            return ch["id"]
    body = {"name": name, "type": kind, "parent_id": parent_id}
    if topic:
        body["topic"] = topic
    if read_only_for_everyone:
        # The @everyone role's id is always the guild id itself.
        body["permission_overwrites"] = [
            {"id": guild_id, "type": 0, "deny": str(SEND_MESSAGES)}
        ]
    ch = _request(token, "POST", f"/guilds/{guild_id}/channels", body)
    existing.append(ch)
    print(f"  #{name} created")
    return ch["id"]


# -- the layout ---------------------------------------------------------------

CATEGORIES = [
    {
        "name": "📢 INFORMATION",
        "channels": [
            {"name": "welcome", "kind": TEXT, "topic": "Start here."},
            {"name": "announcements", "kind": TEXT, "topic": "Releases and news.", "read_only": True},
            {"name": "rules", "kind": TEXT, "topic": "Server rules.", "read_only": True},
        ],
    },
    {
        "name": "💬 COMMUNITY",
        "channels": [
            {"name": "general", "kind": TEXT},
            {"name": "showcase", "kind": TEXT, "topic": "Built something with EndoCore? Show it off."},
            {"name": "off-topic", "kind": TEXT},
        ],
    },
    {
        "name": "🛠️ DEVELOPMENT",
        "channels": [
            {"name": "dev-discussion", "kind": TEXT, "topic": "Framework internals, design decisions."},
            {"name": "contributing", "kind": TEXT, "topic": "See docs/contributing.md."},
            {"name": "bug-reports", "kind": TEXT},
            {"name": "feature-requests", "kind": TEXT},
        ],
    },
    {
        "name": "🆘 SUPPORT",
        "channels": [
            {"name": "help", "kind": TEXT, "topic": "Stuck? Ask here."},
            {"name": "orm-questions", "kind": TEXT},
            {"name": "deployment-questions", "kind": TEXT},
        ],
    },
    {
        "name": "🇷🇺 RU-СООБЩЕСТВО",
        "channels": [
            {"name": "общий", "kind": TEXT, "topic": "Общение на русском."},
            {"name": "помощь", "kind": TEXT, "topic": "Вопросы и помощь на русском."},
            {"name": "обсуждение", "kind": TEXT, "topic": "Обсуждение фреймворка на русском."},
        ],
    },
    {
        "name": "🔊 VOICE",
        "channels": [
            {"name": "General Voice", "kind": VOICE},
            {"name": "Dev Hangout", "kind": VOICE},
        ],
    },
]

ROLES = [
    {"name": "Maintainer", "color": 0xE74C3C, "hoist": True, "mentionable": True},
    {"name": "Contributor", "color": 0x3498DB, "hoist": True, "mentionable": True},
    {"name": "Member", "color": 0x2ECC71, "hoist": False, "mentionable": False},
]


def main() -> None:
    token = os.environ.get("DISCORD_BOT_TOKEN")
    guild_id = os.environ.get("DISCORD_GUILD_ID")
    if not token or not guild_id:
        raise SystemExit(
            "Set DISCORD_BOT_TOKEN and DISCORD_GUILD_ID environment variables first."
        )

    print("Roles:")
    existing_roles = _request(token, "GET", f"/guilds/{guild_id}/roles")
    for role in ROLES:
        ensure_role(token, guild_id, existing_roles, **role)

    print("\nChannels:")
    existing_channels = _request(token, "GET", f"/guilds/{guild_id}/channels")
    for position, category in enumerate(CATEGORIES):
        cat_id = ensure_category(token, guild_id, existing_channels, category["name"], position)
        for ch in category["channels"]:
            ensure_channel(
                token, guild_id, existing_channels, ch["name"],
                kind=ch["kind"], parent_id=cat_id, topic=ch.get("topic", ""),
                read_only_for_everyone=ch.get("read_only", False),
            )

    print("\nDone. The bot's work here is finished — kick it from the server whenever you like.")


if __name__ == "__main__":
    main()
