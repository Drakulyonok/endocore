# Maintainer scripts

Not part of the published package (excluded from the sdist/wheel by
`pyproject.toml`'s `packages.find`) — one-off tooling for running the project.

## `discord_setup.py`

Provisions the EndoCore community Discord server's channel/role layout. See
the module docstring for the Developer Portal walkthrough and usage. Safe to
re-run — everything is looked up by name before creating anything.

```bash
DISCORD_BOT_TOKEN=... DISCORD_GUILD_ID=... python scripts/discord_setup.py
```
