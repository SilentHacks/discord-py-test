"""discord-py-test: offline testing framework for discord.py bots.

Run your real, unmodified bot against a virtual in-memory Discord — no
network, no tokens, no Terms of Service concerns — and test prefix commands,
slash commands, components, permissions and events the way a user exercises
them.

Typical usage::

    import discord_py_test as dpt

    async with dpt.run(bot) as env:
        guild = env.create_guild()
        channel = guild.create_text_channel("general")
        alice = guild.add_member(env.create_user("alice"))

        await alice.send(channel, "!ping")
        assert channel.last_message.content == "Pong!"
"""

from .env import Env, run
from .errors import BackendError, RouteNotImplemented, SetupError
from .handles import (
    ChannelHandle,
    GuildHandle,
    InteractionResult,
    MemberActor,
    ResponseMessage,
    RoleHandle,
    UserHandle,
)

__version__ = "0.1.0"

__all__ = (
    "BackendError",
    "ChannelHandle",
    "Env",
    "GuildHandle",
    "InteractionResult",
    "MemberActor",
    "ResponseMessage",
    "RoleHandle",
    "RouteNotImplemented",
    "SetupError",
    "UserHandle",
    "run",
)
