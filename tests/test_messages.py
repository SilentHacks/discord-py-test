import discord
import pytest
from discord.ext import commands

import discord_py_test as dpt


async def test_prefix_command_round_trip(env, channel, alice):
    await alice.send(channel, "!ping")

    reply = channel.last_message
    assert reply.author == env.bot.user
    assert reply.content == "Pong!"


async def test_member_converter(env, channel, alice):
    await alice.send(channel, f"!whois {alice.mention}")
    assert channel.last_message.content == "That is alice"


async def test_bot_cannot_send_without_permission(env, alice):
    everyone = env.guild.default_role
    env.guild.create_text_channel(
        "locked", overwrites={everyone: discord.PermissionOverwrite(send_messages=False)}
    )
    general = env.guild.create_text_channel("general")

    await alice.send(general, "!announce-to-locked hello")

    assert env.errors, "the bot's Forbidden error should have been captured"
    error = env.errors[-1]
    assert isinstance(error, commands.CommandInvokeError)
    assert isinstance(error.original, discord.Forbidden)
    assert error.original.code == 50013


async def test_user_cannot_speak_where_not_allowed(env, alice):
    hidden = env.guild.create_text_channel(
        "hidden", overwrites={env.guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    )
    with pytest.raises(dpt.BackendError):
        await alice.send(hidden, "sneaky")


async def test_message_edit_and_delete(env, channel):
    ch = env.bot.get_channel(channel.id)
    message = await ch.send("v1")
    edited = await message.edit(content="v2")
    assert edited.content == "v2"
    await edited.delete()
    assert channel.history() == []


async def test_content_limit_enforced(env, channel):
    ch = env.bot.get_channel(channel.id)
    with pytest.raises(discord.HTTPException) as exc_info:
        await ch.send("x" * 2001)
    assert exc_info.value.code == 50035
