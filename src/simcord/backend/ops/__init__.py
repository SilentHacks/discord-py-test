"""Subsystem mixins composing the :class:`~simcord.backend.state.Backend`.

The historical ``Backend`` was a single ~1400-line class. It is split here into a
shared :class:`~simcord.backend.ops.base.BackendBase` kernel plus one mixin per
subsystem; ``state.py`` assembles them into the concrete ``Backend``. Every
method body moved verbatim — this is a pure structural split, not a rewrite.

Why a *shared base + mixins* rather than a naive file split? Two things break a
naive split under ``pyright``:

1. **Cross-subsystem method calls.** ``Backend`` methods call each other across
   feature boundaries (``create_guild`` -> ``add_member``, ``delete_channel`` ->
   ``delete_stage_instance``, ``create_message`` -> ``_auto_mod_blocks``). A mixin
   method calling ``self.method_from_another_mixin()`` fails type-checking,
   because that mixin's ``self`` type doesn't declare the other mixin's methods.
2. **Serializers receive ``self``.** ``serializers.foo(self, ...)`` passes the
   backend; those functions are typed ``backend: BackendBase`` (widened from
   ``Backend`` for exactly this reason), so any mixin ``self`` is assignable.

The design resolves both without ``# type: ignore``, Protocols, or per-method
``self: Backend`` annotations:

- :class:`BackendBase` is the kernel every mixin inherits: the constructor (all
  instance state), the virtual clock/id helpers, the gateway ``emit``, the
  universal getters, and ``compute_permissions``. Because every mixin inherits
  it, any kernel member resolves from every mixin. A member belongs here only
  when it is genuinely cross-cutting (a concrete pyright error on a sibling
  mixin is the signal to pull it up) — not merely because it might be reused.
- **Coupling-aligned boundaries** keep tightly-coupled methods in the *same*
  mixin, so every remaining cross-mixin call targets only the kernel. guilds +
  members + roles live together; channels + threads + stage instances together;
  messages + auto-moderation together.

Most mixins are coupling-aligned clusters. :class:`ExpressionsMixin` is the one
exception: emojis, application emojis, and stickers share no intra-mixin calls
and are grouped by their shared REST surface (``/emojis``, ``/stickers``) rather
than by coupling.

Assembly relies on a clean MRO: every mixin's only base is ``BackendBase``, so
C3 places it once at the tail and only it defines ``__init__`` — ``Backend()``
runs the constructor exactly once. **No mixin may define ``__init__`` or carry
state of its own.**
"""

from __future__ import annotations

from .audit import AuditLogMixin
from .base import BackendBase, EventListener
from .channels import ChannelMixin
from .commands import CommandsMixin
from .expressions import ExpressionsMixin
from .guilds import DEFAULT_EVERYONE_PERMISSIONS, GuildMixin
from .invites import InviteMixin
from .messages import MessageMixin
from .permissions import PermissionsMixin
from .polls import PollMixin
from .reactions import ReactionMixin
from .scheduled_events import ScheduledEventMixin
from .voice import VoiceStateMixin
from .webhooks import WebhookMixin

__all__ = [
    "DEFAULT_EVERYONE_PERMISSIONS",
    "AuditLogMixin",
    "BackendBase",
    "ChannelMixin",
    "CommandsMixin",
    "EventListener",
    "ExpressionsMixin",
    "GuildMixin",
    "InviteMixin",
    "MessageMixin",
    "PermissionsMixin",
    "PollMixin",
    "ReactionMixin",
    "ScheduledEventMixin",
    "VoiceStateMixin",
    "WebhookMixin",
]
