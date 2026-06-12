"""Result/capture objects returned by actor verbs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord

from .backend import serializers
from .backend.errors import BackendError
from .backend.models import EPHEMERAL_FLAG, Message

if TYPE_CHECKING:
    from .env import Env


def to_discord_message(env: Env, message: Message) -> discord.Message:
    """Build a real ``discord.Message`` (bound to the bot's state) from backend state."""
    from ._dpy_internals import get_state

    state = get_state(env.bot)
    channel = env.bot.get_channel(message.channel_id)
    payload = serializers.message_payload(env.backend, message)
    return discord.Message(state=state, channel=channel, data=payload)  # type: ignore[arg-type]


class ResponseMessage:
    """A message the bot sent in response to an interaction."""

    def __init__(self, env: Env, message: Message) -> None:
        self._env = env
        self._message = message

    @property
    def id(self) -> int:
        return self._message.id

    @property
    def channel_id(self) -> int:
        return self._message.channel_id

    @property
    def content(self) -> str:
        return self._message.content

    @property
    def embeds(self) -> list[discord.Embed]:
        return [discord.Embed.from_dict(e) for e in self._message.embeds]

    @property
    def components(self) -> list[dict[str, Any]]:
        return list(self._message.components)

    @property
    def ephemeral(self) -> bool:
        return bool(self._message.flags & EPHEMERAL_FLAG)

    @property
    def message(self) -> discord.Message:
        return to_discord_message(self._env, self._message)

    def __repr__(self) -> str:
        return f"<ResponseMessage id={self.id} content={self.content!r} ephemeral={self.ephemeral}>"


class InteractionResult:
    """Everything that happened in response to a simulated interaction."""

    def __init__(self, env: Env, record: dict[str, Any]) -> None:
        self._env = env
        self.record = record

    @property
    def acknowledged(self) -> bool:
        return self.record["responded"]

    @property
    def deferred(self) -> bool:
        return self.record["response_kind"] in ("deferred", "deferred_update")

    @property
    def ephemeral(self) -> bool:
        return self.record["ephemeral"]

    @property
    def modal(self) -> dict[str, Any] | None:
        """The raw modal payload, if the bot responded with a modal."""
        return self.record["modal"]

    @property
    def autocomplete_choices(self) -> list[dict[str, Any]] | None:
        return self.record["autocomplete_choices"]

    @property
    def response(self) -> ResponseMessage | None:
        if self.record["message_id"] is None:
            return None
        message = self._env.backend.get_message(self.record["channel_id"], self.record["message_id"])
        return ResponseMessage(self._env, message)

    @property
    def followups(self) -> list[ResponseMessage]:
        out = []
        for message_id in self.record["followup_ids"]:
            try:
                message = self._env.backend.get_message(self.record["channel_id"], message_id)
            except BackendError:
                continue  # deleted followup (Unknown Message)
            out.append(ResponseMessage(self._env, message))
        return out

    def __repr__(self) -> str:
        return (
            f"<InteractionResult acknowledged={self.acknowledged} kind={self.record['response_kind']!r} "
            f"response={self.response!r} followups={len(self.followups)}>"
        )
