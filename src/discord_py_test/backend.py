"""The virtual Discord backend: a single in-memory source of truth.

All state (users, guilds, channels, messages, application commands,
interactions, CDN blobs) lives here as Discord wire-format payload dicts.
REST handlers and gateway events are both projections of this state, which is
what keeps the bot's view of the world consistent: every mutation that real
Discord would announce over the gateway is broadcast to attached clients.
"""

from __future__ import annotations

import datetime
from typing import Any, Callable, Iterable, Optional

import discord

from . import errors

# Fixed virtual clock epoch (2026-01-01 UTC) so snowflakes/timestamps are reproducible.
_VIRTUAL_EPOCH_MS = 1767225600000
_DISCORD_EPOCH_MS = 1420070400000

#: Default permissions for a fresh guild's @everyone role.
DEFAULT_EVERYONE_PERMISSIONS = discord.Permissions(
    view_channel=True,
    send_messages=True,
    send_messages_in_threads=True,
    read_message_history=True,
    add_reactions=True,
    embed_links=True,
    attach_files=True,
    external_emojis=True,
    change_nickname=True,
    connect=True,
    speak=True,
    use_application_commands=True,
    create_public_threads=True,
).value

CDN_BASE = "https://cdn.dpt.invalid"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class Backend:
    """Owns all virtual Discord state and broadcasts gateway events."""

    def __init__(self) -> None:
        self._counter = 0
        self.users: dict[int, dict[str, Any]] = {}
        self.guilds: dict[int, dict[str, Any]] = {}
        self.channels: dict[int, dict[str, Any]] = {}
        self.messages: dict[int, dict[int, dict[str, Any]]] = {}  # channel id -> message id -> payload
        self.commands: dict[Optional[int], dict[str, dict[str, Any]]] = {}  # guild id (None=global) -> name -> payload
        self.interactions: dict[int, dict[str, Any]] = {}
        self.interaction_tokens: dict[str, int] = {}
        self.cdn: dict[str, bytes] = {}
        self.subscribers: list[Callable[[str, dict[str, Any]], None]] = []
        self.application_id: int = self.snowflake()
        self.bot_user: dict[str, Any] = self.make_user("TestBot", bot=True)

    # ------------------------------------------------------------------ core

    def snowflake(self) -> int:
        """Deterministic, monotonic snowflakes with valid embedded timestamps."""
        self._counter += 1
        ms = _VIRTUAL_EPOCH_MS - _DISCORD_EPOCH_MS + self._counter
        return (ms << 22) | (self._counter % 4096)

    def emit(self, event: str, payload: dict[str, Any]) -> None:
        for feed in self.subscribers:
            feed(event, payload)

    # ----------------------------------------------------------------- users

    def make_user(self, name: str, *, bot: bool = False) -> dict[str, Any]:
        user = {
            "id": str(self.snowflake()),
            "username": name,
            "discriminator": "0",
            "global_name": name,
            "avatar": None,
            "bot": bot,
            "system": False,
            "public_flags": 0,
            "verified": True,
            "mfa_enabled": False,
            "locale": "en-US",
            "flags": 0,
        }
        self.users[int(user["id"])] = user
        return user

    # ---------------------------------------------------------------- guilds

    def create_guild(self, name: str, *, owner_id: Optional[int] = None) -> dict[str, Any]:
        guild_id = self.snowflake()
        if owner_id is None:
            # A synthetic owner: the bot must never own guilds by default,
            # since owners bypass every permission check.
            owner_id = int(self.make_user(f"{name} Owner")["id"])
        everyone = {
            "id": str(guild_id),
            "name": "@everyone",
            "permissions": str(DEFAULT_EVERYONE_PERMISSIONS),
            "position": 0,
            "color": 0,
            "hoist": False,
            "managed": False,
            "mentionable": False,
            "flags": 0,
            "icon": None,
            "unicode_emoji": None,
        }
        guild = {
            "id": str(guild_id),
            "name": name,
            "owner_id": str(owner_id),
            "roles": {guild_id: everyone},
            "members": {},
            "channel_ids": [],
            "bans": {},
            "features": [],
        }
        self.guilds[guild_id] = guild
        # The bot is always a member of guilds it can see. It gets a managed
        # integration role with broad permissions — like a typical bot invite —
        # but not administrator, so channel overwrites still apply to it.
        bot_permissions = discord.Permissions.all()
        bot_permissions.administrator = False
        bot_role = {
            "id": str(self.snowflake()),
            "name": self.bot_user["username"],
            "permissions": str(bot_permissions.value),
            "position": 1,
            "color": 0,
            "hoist": False,
            "managed": True,
            "mentionable": False,
            "flags": 0,
            "icon": None,
            "unicode_emoji": None,
        }
        guild["roles"][int(bot_role["id"])] = bot_role
        self.add_member(guild_id, int(self.bot_user["id"]), roles=[int(bot_role["id"])])
        self.emit("GUILD_CREATE", self.guild_payload(guild_id))
        return guild

    def guild_payload(self, guild_id: int) -> dict[str, Any]:
        guild = self.guilds[guild_id]
        return {
            "id": guild["id"],
            "name": guild["name"],
            "owner_id": guild["owner_id"],
            "icon": None,
            "splash": None,
            "discovery_splash": None,
            "banner": None,
            "description": None,
            "afk_channel_id": None,
            "afk_timeout": 300,
            "verification_level": 0,
            "default_message_notifications": 0,
            "explicit_content_filter": 0,
            "mfa_level": 0,
            "nsfw_level": 0,
            "premium_tier": 0,
            "premium_subscription_count": 0,
            "preferred_locale": "en-US",
            "system_channel_id": None,
            "system_channel_flags": 0,
            "rules_channel_id": None,
            "public_updates_channel_id": None,
            "vanity_url_code": None,
            "application_id": None,
            "max_members": 500000,
            "max_presences": None,
            "features": guild["features"],
            "emojis": [],
            "stickers": [],
            "roles": list(guild["roles"].values()),
            "member_count": len(guild["members"]),
            "large": False,
            "unavailable": False,
            "joined_at": _now_iso(),
            "members": [self.member_payload(guild_id, uid) for uid in guild["members"]],
            "channels": [self.channels[cid] for cid in guild["channel_ids"]],
            "threads": [],
            "presences": [],
            "voice_states": [],
            "stage_instances": [],
            "guild_scheduled_events": [],
            "soundboard_sounds": [],
            "premium_progress_bar_enabled": False,
        }

    def get_guild(self, guild_id: int) -> dict[str, Any]:
        try:
            return self.guilds[guild_id]
        except KeyError:
            raise errors.unknown("Guild", 10004) from None

    # --------------------------------------------------------------- members

    def add_member(
        self,
        guild_id: int,
        user_id: int,
        *,
        roles: Iterable[int] = (),
        nick: Optional[str] = None,
        announce: bool = False,
    ) -> dict[str, Any]:
        guild = self.get_guild(guild_id)
        member = {
            "user_id": user_id,
            "roles": [str(r) for r in roles],
            "nick": nick,
            "joined_at": _now_iso(),
            "premium_since": None,
            "deaf": False,
            "mute": False,
            "pending": False,
            "flags": 0,
            "communication_disabled_until": None,
            "avatar": None,
        }
        guild["members"][user_id] = member
        if announce:
            payload = self.member_payload(guild_id, user_id)
            payload["guild_id"] = guild["id"]
            self.emit("GUILD_MEMBER_ADD", payload)
        return member

    def remove_member(self, guild_id: int, user_id: int) -> None:
        guild = self.get_guild(guild_id)
        if user_id not in guild["members"]:
            raise errors.unknown("Member", 10007)
        del guild["members"][user_id]
        self.emit(
            "GUILD_MEMBER_REMOVE",
            {"guild_id": guild["id"], "user": self.users[user_id]},
        )

    def member_payload(self, guild_id: int, user_id: int, *, with_user: bool = True) -> dict[str, Any]:
        member = self.get_guild(guild_id)["members"][user_id]
        payload = {k: v for k, v in member.items() if k != "user_id"}
        if with_user:
            payload["user"] = self.users[user_id]
        return payload

    # ----------------------------------------------------------------- roles

    def create_role(self, guild_id: int, name: str, *, permissions: int = 0, **fields: Any) -> dict[str, Any]:
        guild = self.get_guild(guild_id)
        role = {
            "id": str(self.snowflake()),
            "name": name,
            "permissions": str(permissions),
            "position": len(guild["roles"]),
            "color": 0,
            "hoist": False,
            "managed": False,
            "mentionable": False,
            "flags": 0,
            "icon": None,
            "unicode_emoji": None,
        }
        role.update(fields)
        guild["roles"][int(role["id"])] = role
        self.emit("GUILD_ROLE_CREATE", {"guild_id": guild["id"], "role": role})
        return role

    # -------------------------------------------------------------- channels

    def create_channel(
        self,
        guild_id: int,
        name: str,
        *,
        type: int = 0,
        overwrites: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        guild = self.get_guild(guild_id)
        channel = {
            "id": str(self.snowflake()),
            "type": type,
            "guild_id": guild["id"],
            "name": name,
            "position": len(guild["channel_ids"]),
            "permission_overwrites": overwrites or [],
            "nsfw": False,
            "parent_id": None,
            "topic": None,
            "rate_limit_per_user": 0,
            "last_message_id": None,
        }
        cid = int(channel["id"])
        self.channels[cid] = channel
        self.messages[cid] = {}
        guild["channel_ids"].append(cid)
        self.emit("CHANNEL_CREATE", channel)
        return channel

    def get_channel(self, channel_id: int) -> dict[str, Any]:
        try:
            return self.channels[channel_id]
        except KeyError:
            raise errors.unknown("Channel", 10003) from None

    # ------------------------------------------------------------ permissions

    def compute_permissions(self, guild_id: int, user_id: int, channel_id: Optional[int] = None) -> int:
        """Effective permissions per Discord's documented algorithm."""
        guild = self.get_guild(guild_id)
        all_perms = discord.Permissions.all().value
        if int(guild["owner_id"]) == user_id:
            return all_perms
        member = guild["members"].get(user_id)
        if member is None:
            return 0
        base = int(guild["roles"][guild_id]["permissions"])
        for role_id in member["roles"]:
            role = guild["roles"].get(int(role_id))
            if role:
                base |= int(role["permissions"])
        if base & discord.Permissions.administrator.flag:
            return all_perms
        if channel_id is not None:
            channel = self.get_channel(channel_id)
            overwrites = channel["permission_overwrites"]
            by_id = {int(o["id"]): o for o in overwrites}
            # @everyone overwrite
            everyone_ow = by_id.get(guild_id)
            if everyone_ow:
                base = (base & ~int(everyone_ow["deny"])) | int(everyone_ow["allow"])
            allow = deny = 0
            for role_id in member["roles"]:
                ow = by_id.get(int(role_id))
                if ow and int(ow["type"]) == 0:
                    allow |= int(ow["allow"])
                    deny |= int(ow["deny"])
            base = (base & ~deny) | allow
            member_ow = by_id.get(user_id)
            if member_ow and int(member_ow["type"]) == 1:
                base = (base & ~int(member_ow["deny"])) | int(member_ow["allow"])
        return base

    def require_permissions(self, guild_id: Optional[int], user_id: int, channel_id: Optional[int], *names: str) -> None:
        if guild_id is None:  # DMs: no guild permissions apply
            return
        perms = self.compute_permissions(guild_id, user_id, channel_id)
        view = discord.Permissions.view_channel.flag
        if channel_id is not None and not perms & view:
            raise errors.missing_access()
        for name in names:
            if not perms & getattr(discord.Permissions, name).flag:
                raise errors.missing_permissions()

    # -------------------------------------------------------------- messages

    def create_message(
        self,
        channel_id: int,
        author_id: int,
        content: str = "",
        *,
        embeds: Optional[list[dict[str, Any]]] = None,
        components: Optional[list[dict[str, Any]]] = None,
        attachments: Optional[list[dict[str, Any]]] = None,
        flags: int = 0,
        message_reference: Optional[dict[str, Any]] = None,
        interaction_metadata: Optional[dict[str, Any]] = None,
        broadcast: bool = True,
    ) -> dict[str, Any]:
        channel = self.get_channel(channel_id)
        if content and len(content) > 2000:
            raise errors.BackendError(400, 50035, "Invalid Form Body: content must be 2000 or fewer in length")
        guild_id = int(channel["guild_id"]) if channel.get("guild_id") else None
        message = {
            "id": str(self.snowflake()),
            "channel_id": channel["id"],
            "author": self.users[author_id],
            "content": content or "",
            "timestamp": _now_iso(),
            "edited_timestamp": None,
            "tts": False,
            "mention_everyone": False,
            "mentions": [],
            "mention_roles": [],
            "attachments": attachments or [],
            "embeds": embeds or [],
            "pinned": False,
            "type": 19 if message_reference else 0,
            "flags": flags,
            "components": components or [],
            "reactions": [],
            "nonce": None,
        }
        if guild_id is not None:
            message["guild_id"] = channel["guild_id"]
        if message_reference:
            message["message_reference"] = message_reference
            ref = self.messages.get(int(message_reference["channel_id"]), {}).get(
                int(message_reference["message_id"])
            )
            if ref:
                message["referenced_message"] = ref
        if interaction_metadata:
            message["interaction_metadata"] = interaction_metadata
        self.messages[channel_id][int(message["id"])] = message
        channel["last_message_id"] = message["id"]
        if broadcast:
            payload = dict(message)
            if guild_id is not None and author_id in self.guilds[guild_id]["members"]:
                payload["member"] = self.member_payload(guild_id, author_id, with_user=False)
            self.emit("MESSAGE_CREATE", payload)
        return message

    def get_message(self, channel_id: int, message_id: int) -> dict[str, Any]:
        msg = self.messages.get(channel_id, {}).get(message_id)
        if msg is None:
            raise errors.unknown("Message", 10008)
        return msg

    def edit_message(self, channel_id: int, message_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        message = self.get_message(channel_id, message_id)
        for key in ("content", "embeds", "components", "flags", "attachments"):
            if key in fields and fields[key] is not None:
                message[key] = fields[key]
        message["edited_timestamp"] = _now_iso()
        self.emit("MESSAGE_UPDATE", dict(message))
        return message

    def delete_message(self, channel_id: int, message_id: int) -> None:
        self.get_message(channel_id, message_id)
        del self.messages[channel_id][message_id]
        channel = self.get_channel(channel_id)
        payload = {"id": str(message_id), "channel_id": str(channel_id)}
        if channel.get("guild_id"):
            payload["guild_id"] = channel["guild_id"]
        self.emit("MESSAGE_DELETE", payload)

    # --------------------------------------------------- application commands

    def register_commands(self, guild_id: Optional[int], payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        registered = {}
        for payload in payloads:
            cmd = dict(payload)
            cmd["id"] = str(self.snowflake())
            cmd["application_id"] = str(self.application_id)
            cmd.setdefault("type", 1)
            cmd.setdefault("description", "")
            cmd.setdefault("options", [])
            cmd.setdefault("default_member_permissions", None)
            cmd.setdefault("nsfw", False)
            cmd.setdefault("dm_permission", True)
            if guild_id is not None:
                cmd["guild_id"] = str(guild_id)
            registered[cmd["name"]] = cmd
        self.commands[guild_id] = registered
        return list(registered.values())

    def find_command(self, name: str, guild_id: Optional[int], type: int = 1) -> Optional[dict[str, Any]]:
        for scope in (guild_id, None):
            cmd = self.commands.get(scope, {}).get(name)
            if cmd is not None and cmd.get("type", 1) == type:
                return cmd
        return None

    # ----------------------------------------------------------- interactions

    def new_interaction(self, type: int, channel_id: int, user_id: int, guild_id: Optional[int]) -> dict[str, Any]:
        iid = self.snowflake()
        record = {
            "id": iid,
            "token": f"dpt_interaction_{iid}",
            "type": type,
            "channel_id": channel_id,
            "guild_id": guild_id,
            "user_id": user_id,
            "responded": False,
            "response_kind": None,  # 'message' | 'deferred' | 'modal' | 'autocomplete' | 'update'
            "message_id": None,  # the response message
            "source_message_id": None,  # for component interactions
            "ephemeral": False,
            "followup_ids": [],
            "modal": None,
            "autocomplete_choices": None,
        }
        self.interactions[iid] = record
        self.interaction_tokens[record["token"]] = iid
        return record

    def interaction_by_token(self, token: str) -> dict[str, Any]:
        iid = self.interaction_tokens.get(token)
        if iid is None:
            raise errors.unknown("Webhook", 10015)
        return self.interactions[iid]

    # ------------------------------------------------------------------- CDN

    def store_attachment(self, channel_id: int, filename: str, data: bytes, description: Optional[str]) -> dict[str, Any]:
        aid = self.snowflake()
        url = f"{CDN_BASE}/attachments/{channel_id}/{aid}/{filename}"
        self.cdn[url] = data
        return {
            "id": str(aid),
            "filename": filename,
            "description": description,
            "size": len(data),
            "url": url,
            "proxy_url": url,
            "content_type": None,
        }
