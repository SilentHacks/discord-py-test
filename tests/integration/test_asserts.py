import discord
import pytest

import simcord
from fixtures.sample_bot import create_bot
from simcord import (
    assert_error,
    assert_message,
    assert_no_errors,
    assert_responded,
    assert_sent,
)

# ----------------------------------------------------------------- assert_sent


async def test_assert_sent_matches(channel, alice):
    await alice.send(channel, "!ping")
    assert_sent(channel, content="Pong!")
    assert_sent(channel, contains="Pong")


async def test_assert_sent_mismatch_shows_recent_history(channel, alice):
    await alice.send(channel, "!ping")
    with pytest.raises(AssertionError) as exc:
        assert_sent(channel, content="nope")
    message = str(exc.value)
    assert "'nope'" in message
    assert "'Pong!'" in message  # the actual content is shown


async def test_assert_sent_when_nothing_sent(env):
    empty = env.guild.create_text_channel("empty")
    with pytest.raises(AssertionError, match="none was sent"):
        assert_sent(empty, content="anything")


# ------------------------------------------------------------ assert_responded


async def test_assert_responded_matches(channel, alice):
    result = await alice.slash(channel, "config set", key="lang", value="en")
    assert_responded(result, content="lang=en")


async def test_assert_responded_ephemeral(env, channel, alice):
    bob = env.guild.add_member(env.create_user("bob"))
    result = await alice.context_menu(channel, "Report Member", bob)
    assert_responded(result, content="Reported bob", ephemeral=True)


async def test_assert_responded_mismatch_shows_result(channel, alice):
    result = await alice.slash(channel, "config set", key="lang", value="en")
    with pytest.raises(AssertionError) as exc:
        assert_responded(result, content="wrong")
    assert "lang=en" in str(exc.value)


# -------------------------------------------------------------- assert_message


async def test_assert_message_on_real_discord_message(channel, alice):
    await alice.send(channel, "!ping")
    assert_message(channel.last_message, content="Pong!")


async def test_assert_message_on_response(channel, alice):
    result = await alice.slash(channel, "config set", key="lang", value="en")
    assert_message(result.response, content="lang=en")


# ---------------------------------------------------------------- assert_error


async def test_assert_error_matches_wrapped_original(env, channel, alice):
    env.inject_error("POST", "/channels/*/messages", status=403, code=50013, times=None)
    await alice.send(channel, "!ping")

    error = assert_error(env, discord.Forbidden, code=50013)
    assert error is not None


async def test_assert_error_none_captured(env):
    with pytest.raises(AssertionError, match="captured none"):
        assert_error(env, discord.Forbidden)


async def test_assert_error_no_match_lists_captured(env, channel, alice):
    env.inject_error("POST", "/channels/*/messages", status=403, code=50013, times=None)
    await alice.send(channel, "!ping")

    with pytest.raises(AssertionError, match="no captured error matched"):
        assert_error(env, KeyError)


# ------------------------------------------------------------ assert_no_errors


async def test_assert_no_errors_on_clean_run(env, channel, alice):
    await alice.send(channel, "!ping")
    assert_no_errors(env)


async def test_assert_no_errors_raises_when_bot_failed(env, channel, alice):
    env.inject_error("POST", "/channels/*/messages", status=403, code=50013, times=None)
    await alice.send(channel, "!ping")

    with pytest.raises(BaseExceptionGroup):
        assert_no_errors(env)


# --------------------------------------------------------- create_guild(id=...)


async def test_create_guild_with_pinned_id():
    bot = create_bot()
    async with simcord.run(bot) as env:
        guild = env.create_guild(id=987654321012345678)
        assert guild.id == 987654321012345678
