from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Discord channel types
GUILD_TEXT = 0
DM = 1
GUILD_VOICE = 2
GUILD_CATEGORY = 4
PUBLIC_THREAD = 11
PRIVATE_THREAD = 12

THREAD_TYPES = (PUBLIC_THREAD, PRIVATE_THREAD)


@dataclass
class Overwrite:
    target_id: int
    type: int  # 0 = role, 1 = member
    allow: int = 0
    deny: int = 0


@dataclass
class ThreadMetadata:
    archived: bool = False
    auto_archive_duration: int = 1440
    archive_timestamp: str = ""
    locked: bool = False
    create_timestamp: str = ""


@dataclass
class Channel:
    id: int
    type: int
    name: Optional[str] = None
    guild_id: Optional[int] = None
    position: int = 0
    overwrites: list[Overwrite] = field(default_factory=list)
    topic: Optional[str] = None
    parent_id: Optional[int] = None
    nsfw: bool = False
    rate_limit_per_user: int = 0
    last_message_id: Optional[int] = None
    recipient_ids: list[int] = field(default_factory=list)  # DM channels
    # Thread-only fields
    owner_id: Optional[int] = None
    thread_metadata: Optional[ThreadMetadata] = None
    message_count: int = 0

    @property
    def is_thread(self) -> bool:
        return self.type in THREAD_TYPES

    def permission_channel_id(self) -> int:
        """Threads inherit permissions from their parent channel."""
        return self.parent_id if self.is_thread and self.parent_id else self.id
