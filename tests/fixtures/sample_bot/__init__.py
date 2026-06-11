"""A realistic kitchen-sink bot used by the integration tests.

Structured the way real projects are — cogs, views and listeners in separate
modules, loaded as extensions from ``setup_hook`` — so the test suite proves
the framework against the patterns bots actually use.
"""

import discord
from discord.ext import commands

EXTENSIONS = (
    "fixtures.sample_bot.general",
    "fixtures.sample_bot.moderation",
    "fixtures.sample_bot.interactions",
    "fixtures.sample_bot.events",
)


def create_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    # Context menus can't live on cogs declaratively; register one here.
    @bot.tree.context_menu(name="Report")
    async def report(interaction: discord.Interaction, member: discord.Member) -> None:
        await interaction.response.send_message(f"Reported {member.display_name}", ephemeral=True)

    async def setup_hook() -> None:
        for extension in EXTENSIONS:
            await bot.load_extension(extension)
        await bot.tree.sync()

    bot.setup_hook = setup_hook
    return bot
