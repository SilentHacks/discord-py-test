import discord
import pytest


async def test_actor_joins_voice(env, channel, alice):
    voice = env.guild.create_voice_channel("General Voice")
    await env.settle()

    await alice.join_voice(voice, self_mute=True)

    guild = env.bot.get_guild(env.guild.id)
    member = guild.get_member(alice.id)
    assert member.voice is not None
    assert member.voice.channel.id == voice.id
    assert member.voice.self_mute is True
    assert "VOICE_STATE_UPDATE" in env.transcript()


async def test_actor_leaves_voice(env, channel, alice):
    voice = env.guild.create_voice_channel("General Voice")
    await env.settle()
    await alice.join_voice(voice)
    await alice.leave_voice()

    member = env.bot.get_guild(env.guild.id).get_member(alice.id)
    assert member.voice is None
    assert alice.id not in env.guild.voice_states()


async def test_server_mute_via_edit(env, channel, alice):
    voice = env.guild.create_voice_channel("General Voice")
    await env.settle()
    await alice.join_voice(voice)

    guild = env.bot.get_guild(env.guild.id)
    await guild.get_member(alice.id).edit(mute=True)
    await env.settle()

    assert env.guild.voice_states()[alice.id].mute is True


async def test_move_member_between_channels(env, channel, alice):
    first = env.guild.create_voice_channel("First")
    second = env.guild.create_voice_channel("Second")
    await env.settle()
    await alice.join_voice(first)

    guild = env.bot.get_guild(env.guild.id)
    await guild.get_member(alice.id).move_to(guild.get_channel(second.id))
    await env.settle()

    assert env.guild.voice_states()[alice.id].channel_id == second.id
    # The move was recorded in the audit log.
    moves = [e for e in env.guild.audit_log() if e.action_type == 26]
    assert moves


async def test_move_disconnected_member_errors(env, channel, alice):
    voice = env.guild.create_voice_channel("General Voice")
    await env.settle()

    guild = env.bot.get_guild(env.guild.id)
    with pytest.raises(discord.HTTPException) as exc:
        await guild.get_member(alice.id).move_to(guild.get_channel(voice.id))
    assert exc.value.code == 40032


async def test_leave_voice_when_not_connected_is_noop(env, channel, alice):
    await alice.leave_voice()

    assert "VOICE_STATE_UPDATE" not in env.transcript()
    assert alice.id not in env.guild.voice_states()


async def test_server_mute_recorded_in_audit_log(env, channel, alice):
    voice = env.guild.create_voice_channel("General Voice")
    await env.settle()
    await alice.join_voice(voice)

    guild = env.bot.get_guild(env.guild.id)
    await guild.get_member(alice.id).edit(mute=True)
    await env.settle()

    updates = [e for e in env.guild.audit_log() if e.action_type == 24]  # MEMBER_UPDATE
    assert updates
    assert any(c["key"] == "mute" and c["new_value"] is True for c in updates[-1].changes)


async def test_sample_bot_voice_log_listener(env, alice):
    voice_log = env.guild.create_text_channel("voice-log")
    voice = env.guild.create_voice_channel("General Voice")
    await env.settle()

    await alice.join_voice(voice)
    assert voice_log.last_message.content == "alice joined General Voice"


async def test_invite_member_to_speak_on_stage(env, alice):
    stage = env.guild.create_stage_channel("Stage")
    await env.settle()
    await alice.join_voice(stage)
    # Audience members are suppressed; the bot invites alice to speak.
    env.backend.get_guild(env.guild.id).voice_states[alice.id].suppress = True

    guild = env.bot.get_guild(env.guild.id)
    await guild.get_member(alice.id).edit(suppress=False)
    await env.settle()

    assert env.guild.voice_states()[alice.id].suppress is False


async def test_request_to_speak_as_bot(env):
    stage = env.guild.create_stage_channel("Stage")
    await env.settle()
    # The bot cannot open a real voice connection, so seed its voice state.
    env.backend.set_voice_state(env.guild.id, env.bot.user.id, stage.id, suppress=True)
    await env.settle()

    guild = env.bot.get_guild(env.guild.id)
    await guild.me.request_to_speak()
    await env.settle()

    assert env.guild.voice_states()[env.bot.user.id].request_to_speak_timestamp is not None


async def test_edit_voice_state_when_disconnected_errors(env, alice):
    env.guild.create_stage_channel("Stage")
    await env.settle()
    guild = env.bot.get_guild(env.guild.id)

    # alice is not connected, so there is no voice state to edit.
    import discord

    with pytest.raises(discord.HTTPException) as exc:
        await guild.get_member(alice.id).edit(suppress=False)
    assert exc.value.code == 40032


async def test_edit_others_voice_state_requires_mute_members(env, alice):
    stage = env.guild.create_stage_channel("Stage")
    await env.settle()
    await alice.join_voice(stage)
    mask = ~discord.Permissions(mute_members=True).value
    for role in env.backend.get_guild(env.guild.id).roles.values():
        role.permissions &= mask

    guild = env.bot.get_guild(env.guild.id)
    with pytest.raises(discord.Forbidden) as exc:
        await guild.get_member(alice.id).edit(suppress=False)
    assert exc.value.code == 50013
