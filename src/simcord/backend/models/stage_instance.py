from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StageInstance:
    """A live stage instance opened on a stage channel."""

    id: int
    guild_id: int
    channel_id: int
    topic: str
    privacy_level: int = 2  # GUILD_ONLY
    discoverable_disabled: bool = True
    scheduled_event_id: int | None = None
