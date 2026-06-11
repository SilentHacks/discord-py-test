from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Reaction:
    emoji: str  # unicode emoji or "name:id" for custom
    user_ids: list[int] = field(default_factory=list)


@dataclass
class Message:
    id: int
    channel_id: int
    author_id: int
    content: str = ""
    timestamp: str = ""
    edited_timestamp: str | None = None
    type: int = 0
    flags: int = 0
    pinned: bool = False
    tts: bool = False
    embeds: list[dict[str, Any]] = field(default_factory=list)
    components: list[dict[str, Any]] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)
    reactions: list[Reaction] = field(default_factory=list)
    mention_user_ids: list[int] = field(default_factory=list)
    mention_role_ids: list[int] = field(default_factory=list)
    mention_everyone: bool = False
    reference: dict[str, Any] | None = None
    interaction_metadata: dict[str, Any] | None = None

    def reaction_for(self, emoji: str) -> Reaction | None:
        for reaction in self.reactions:
            if reaction.emoji == emoji:
                return reaction
        return None
