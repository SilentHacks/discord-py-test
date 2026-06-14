"""Voice state."""

from __future__ import annotations

from typing import Any

from .. import serializers
from ..models import VoiceState
from .base import BackendBase


class VoiceStateMixin(BackendBase):
    def set_voice_state(
        self, guild_id: int, user_id: int, channel_id: int | None, **flags: Any
    ) -> VoiceState | None:
        """Upsert a member's voice state (or disconnect when ``channel_id`` is None).

        Disconnecting a member who is not connected is a no-op (no event), so a
        stray ``leave_voice`` does not emit a spurious VOICE_STATE_UPDATE.
        """
        guild = self.get_guild(guild_id)
        state = guild.voice_states.get(user_id)
        if state is None and channel_id is None:
            return None
        if state is None:
            state = VoiceState(
                user_id=user_id,
                guild_id=guild_id,
                channel_id=channel_id,
                session_id=f"session_{user_id}",
            )
        state.channel_id = channel_id
        for attr, value in flags.items():
            setattr(state, attr, value)
        if channel_id is None:
            guild.voice_states.pop(user_id, None)
        else:
            guild.voice_states[user_id] = state
        self.emit("VOICE_STATE_UPDATE", serializers.voice_state_payload(self, state))
        return state
