"""Audit-log recording (leaf — called only from route handlers)."""

from __future__ import annotations

from typing import Any

from .. import serializers
from ..models import AuditLogEntry
from .base import BackendBase


class AuditLogMixin(BackendBase):
    def record_audit_log(
        self,
        guild_id: int,
        action_type: int,
        *,
        target_id: int | None = None,
        changes: list[dict[str, Any]] | None = None,
        options: dict[str, Any] | None = None,
        reason: str | None = None,
        user_id: int | None = None,
    ) -> AuditLogEntry:
        """Record a privileged action in the guild's audit log and announce it.

        Called from route handlers (the API-call path), never from the backend
        mutation methods themselves — so omnipotent test/builder setup does not
        generate audit entries, exactly as real Discord only logs API actions.
        """
        guild = self.get_guild(guild_id)
        entry = AuditLogEntry(
            id=self.snowflake(),
            action_type=int(action_type),
            user_id=user_id if user_id is not None else self.bot_user.id,
            target_id=target_id,
            reason=reason,
            changes=list(changes or []),
            options=dict(options or {}),
        )
        guild.audit_log_entries.append(entry)
        payload = dict(serializers.audit_log_entry_payload(entry))
        payload["guild_id"] = str(guild_id)
        self.emit("GUILD_AUDIT_LOG_ENTRY_CREATE", payload)
        return entry
