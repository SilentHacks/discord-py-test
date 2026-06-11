from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Member:
    user_id: int
    role_ids: list[int] = field(default_factory=list)
    nick: Optional[str] = None
    joined_at: str = ""
    timed_out_until: Optional[str] = None  # ISO timestamp while timed out
    deaf: bool = False
    mute: bool = False
    pending: bool = False
