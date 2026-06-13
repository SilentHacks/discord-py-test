"""Example test suite using the bundled pytest plugin's `simcord_env` fixture."""

import discord
import pytest


async def test_ping(simcord_env):
    channel = simcord_env.create_guild().create_text_channel("general")
    alice = simcord_env.guild.add_member(simcord_env.create_user("alice"))

    await alice.send(channel, "!ping")

    assert channel.last_message.content == "Pong!"


async def test_ban_requires_permission(simcord_env):
    guild = simcord_env.create_guild()
    channel = guild.create_text_channel("mod")
    mods = guild.create_role("Mods", permissions=discord.Permissions(ban_members=True))
    mod = guild.add_member(simcord_env.create_user("mod"), roles=[mods])
    rando = guild.add_member(simcord_env.create_user("rando"))
    target = guild.add_member(simcord_env.create_user("spammer"))

    denied = await rando.slash(channel, "ban", user=target)
    assert denied.response.content == "You can't do that."
    assert guild.get_ban(target) is None

    allowed = await mod.slash(channel, "ban", user=target, reason="spam")
    assert allowed.ephemeral
    assert allowed.response.content == f"Banned {target.mention}: spam"
    assert guild.get_ban(target) is not None


async def test_env_is_strict_by_default(simcord_env):
    assert simcord_env.strict_sync is True


@pytest.mark.simcord(strict_sync=False)
async def test_marker_forwards_options_to_run(simcord_env):
    # The marker's kwargs reach simcord.run(), so per-test config needs no
    # custom fixture.
    assert simcord_env.strict_sync is False
