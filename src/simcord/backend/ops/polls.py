"""Poll voting and expiry."""

from __future__ import annotations

import datetime
from typing import Any

from .. import errors, serializers
from ..models import Message
from .base import BackendBase


class PollMixin(BackendBase):
    def add_poll_vote(self, channel_id: int, message_id: int, answer_id: int, user_id: int) -> None:
        message = self.get_message(channel_id, message_id)
        poll = message.poll
        if poll is None or poll.answer(answer_id) is None:
            raise errors.invalid_form_body("poll answer does not exist")
        if not poll.allow_multiselect:
            for other_id, voters in poll.votes.items():
                if other_id != answer_id and user_id in voters:
                    voters.discard(user_id)
                    self._emit_poll_vote("MESSAGE_POLL_VOTE_REMOVE", message, other_id, user_id)
        voters = poll.votes.setdefault(answer_id, set())
        if user_id in voters:
            return
        voters.add(user_id)
        self._emit_poll_vote("MESSAGE_POLL_VOTE_ADD", message, answer_id, user_id)

    def remove_poll_vote(self, channel_id: int, message_id: int, answer_id: int, user_id: int) -> None:
        message = self.get_message(channel_id, message_id)
        poll = message.poll
        if poll is None:
            raise errors.invalid_form_body("message has no poll")
        voters = poll.votes.get(answer_id, set())
        if user_id not in voters:
            return
        voters.discard(user_id)
        self._emit_poll_vote("MESSAGE_POLL_VOTE_REMOVE", message, answer_id, user_id)

    def _emit_poll_vote(self, event: str, message: Message, answer_id: int, user_id: int) -> None:
        channel = self.get_channel(message.channel_id)
        payload: dict[str, Any] = {
            "user_id": str(user_id),
            "channel_id": str(message.channel_id),
            "message_id": str(message.id),
            "answer_id": answer_id,
        }
        if channel.guild_id is not None:
            payload["guild_id"] = str(channel.guild_id)
        self.emit(event, payload)

    def expire_poll(self, channel_id: int, message_id: int) -> Message:
        message = self.get_message(channel_id, message_id)
        if message.poll is not None and not message.poll.finalized:
            message.poll.finalized = True
            self.emit("MESSAGE_UPDATE", dict(serializers.message_payload(self, message)))
        return message

    def expire_due_polls(self) -> None:
        """Finalize any polls whose expiry has passed (driven by the virtual clock)."""
        now = datetime.datetime.fromisoformat(self.now_iso())
        for channel_messages in self.messages.values():
            for message in channel_messages.values():
                poll = message.poll
                if poll is None or poll.finalized:
                    continue
                if datetime.datetime.fromisoformat(poll.expiry) <= now:
                    self.expire_poll(message.channel_id, message.id)
