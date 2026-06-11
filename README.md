# discord-py-test

Offline testing framework for [discord.py](https://github.com/Rapptz/discord.py) bots.

Run your **real, unmodified bot** against a virtual, in-memory Discord — no network, no
tokens, no manual clicking through Discord, and no Terms of Service concerns (nothing ever
connects to Discord). Simulate users sending messages, invoking slash commands and clicking
buttons, then assert on exactly what your bot did.

> ⚠️ Alpha software. The core surface (messages, prefix commands, slash commands,
> components, permissions) works; the long tail of the Discord API is still being filled in.
> Unimplemented routes always fail loudly — this library never silently fakes success.

## Why

Unit tests can cover your business logic, but the bugs that bite Discord bots live in the
glue: converters, checks, permissions, forgotten `tree.sync()` calls, double-acknowledged
interactions, oversized embeds. Until now the only way to test that layer was manually, in
a real server. `discord-py-test` runs all of discord.py's real machinery — its parsers,
cache, command frameworks and views — against a faithful fake of Discord's REST API and
gateway, entirely in-process.

- **Real semantics**: permission checks with authentic error codes (`50013 Missing
  Permissions`…), interaction lifecycle rules (`40060` on double-ack), the works.
- **Real bugs caught**: invoking a slash command that was never synced fails your test,
  just like it fails in production.
- **Fast and deterministic**: no sleeps, no network, reproducible IDs. Thousands of tests
  per minute.

## Install

```bash
pip install discord-py-test
```

Requires Python 3.10+ and discord.py 2.7+.

## Quickstart

```python
# conftest.py
import pytest_asyncio
import discord_py_test as dpt
from mybot import create_bot  # however your project builds its commands.Bot

@pytest_asyncio.fixture
async def env():
    async with dpt.run(create_bot()) as env:   # fake login + READY, no network
        env.create_guild()
        yield env
```

```python
# test_bot.py
import discord

async def test_ping(env):
    channel = env.guild.create_text_channel("general")
    alice = env.guild.add_member(env.create_user("alice"))

    await alice.send(channel, "!ping")                    # full gateway round trip

    assert channel.last_message.content == "Pong!"

async def test_ban_slash_command(env):
    channel = env.guild.create_text_channel("mod")
    mods = env.guild.create_role("Mods", permissions=discord.Permissions(ban_members=True))
    mod = env.guild.add_member(env.create_user("mod"), roles=[mods])
    target = env.guild.add_member(env.create_user("spammer"))

    result = await mod.slash(channel, "ban", user=target, reason="spam")

    assert result.ephemeral
    assert result.response.content == f"Banned {target.mention}: spam"
    assert env.guild.get_ban(target) is not None

async def test_confirm_button(env):
    channel = env.guild.create_text_channel("general")
    alice = env.guild.add_member(env.create_user("alice"))

    result = await alice.slash(channel, "delete-data")
    await alice.click(result.response.message, label="Confirm")

    assert result.response.content == "Deleted all data."
```

## How it works

discord.py has two narrow seams: every REST call funnels through
`HTTPClient.request`, and every gateway event enters through
`ConnectionState.parsers`. `discord-py-test` replaces the first with a fake routed to an
in-memory backend (a single source of truth for guilds, channels, members, messages,
commands and interactions) and injects Discord-shaped payloads through the second.
Everything between those seams — which is everything your bot touches — is real
discord.py code running unmodified.

Builders (`env.create_guild()`, `guild.add_member()`) arrange the world omnipotently;
actors (`alice.send(...)`, `alice.slash(...)`, `alice.click(...)`) are permission-checked
and can only do what a real human could do. After every action the framework waits for
your bot to finish reacting — no `asyncio.sleep` guesswork.

## Status / roadmap

Supported today: text channels & messages (embeds, attachments, replies, edits/deletes),
prefix commands, the permissions model (roles + channel overwrites), slash commands with
typed options and resolved data, deferred responses and followups, ephemeral visibility,
buttons, string selects, modals, kick/ban, member join/leave events.

Planned: threads, reactions, webhooks, autocomplete drivers, more channel types,
voice state, a pytest plugin with built-in fixtures, and a public parity matrix.

## Contributing

```bash
git clone https://github.com/SilentHacks/discord-py-test
cd discord-py-test
python -m venv .venv && .venv/bin/pip install -e .[pytest]
.venv/bin/pytest
```

Bug reports with a failing test are gold. If your bot hits an unimplemented route, the
error message names it — please open an issue.

## License

MIT. Not affiliated with Discord Inc. or the discord.py project.
