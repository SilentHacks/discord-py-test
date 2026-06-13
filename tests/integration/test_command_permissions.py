import discord
import pytest


async def test_fetch_command_permissions(env):
    guild = env.bot.get_guild(env.guild.id)
    commands = await env.bot.tree.fetch_commands()
    command = commands[0]

    mods = env.guild.create_role("Mods")
    env.guild.set_command_permissions(command, {mods: True})

    perms = await command.fetch_permissions(guild)
    assert [(p.id, p.permission) for p in perms.permissions] == [(mods.id, True)]


async def test_fetch_command_permissions_not_found_when_default(env):
    guild = env.bot.get_guild(env.guild.id)
    commands = await env.bot.tree.fetch_commands()

    # Unchanged from the guild default: Discord 404s, surfaced as NotFound.
    with pytest.raises(discord.NotFound):
        await commands[0].fetch_permissions(guild)
