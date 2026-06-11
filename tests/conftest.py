import discord
import pytest
import pytest_asyncio
from discord import app_commands
from discord.ext import commands

import discord_py_test as dpt


def create_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.command()
    async def ping(ctx: commands.Context) -> None:
        await ctx.send("Pong!")

    @bot.command()
    async def whois(ctx: commands.Context, member: discord.Member) -> None:
        await ctx.send(f"That is {member.display_name}")

    @bot.tree.command(description="Ban a member")
    @app_commands.describe(user="Who to ban", reason="Why")
    async def ban(interaction: discord.Interaction, user: discord.Member, reason: str = "no reason") -> None:
        if not interaction.permissions.ban_members:
            await interaction.response.send_message("You can't do that.", ephemeral=True)
            return
        await user.ban(reason=reason)
        await interaction.response.send_message(f"Banned {user.mention}: {reason}", ephemeral=True)

    class ConfirmView(discord.ui.View):
        @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
            await interaction.response.edit_message(content="Deleted all data.", view=None)

        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
            await interaction.response.edit_message(content="Cancelled.", view=None)

    @bot.tree.command(name="delete-data", description="Delete your data")
    async def delete_data(interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Are you sure?", view=ConfirmView())

    @bot.tree.command(description="Slow command that defers")
    async def slow(interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await interaction.followup.send("Done after a while")

    @bot.command(name="announce-to-locked")
    async def announce(ctx: commands.Context, *, text: str) -> None:
        locked = discord.utils.get(ctx.guild.text_channels, name="locked")
        await locked.send(text)

    async def setup_hook() -> None:
        await bot.tree.sync()

    bot.setup_hook = setup_hook
    return bot


@pytest_asyncio.fixture
async def env():
    bot = create_bot()
    async with dpt.run(bot) as env:
        env.create_guild()
        yield env


@pytest.fixture
def channel(env):
    return env.guild.create_text_channel("general")


@pytest.fixture
def alice(env):
    return env.guild.add_member(env.create_user("alice"))
