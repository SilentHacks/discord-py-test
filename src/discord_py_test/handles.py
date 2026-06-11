"""Public handles: omnipotent world builders and permission-checked actors.

Builders (``GuildHandle.create_text_channel`` etc.) construct world state
directly — the *test* is omnipotent. Actors (``MemberActor.send`` /
``.slash`` / ``.click``) simulate what a real human could do, are permission
checked, and drive the bot through the same gateway events real Discord would
send.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Sequence, Union

import discord

from .errors import SetupError

if TYPE_CHECKING:
    from .env import Env

# Application command option type -> expected python kind
_OPTION_TYPES = {3: str, 4: int, 5: bool, 10: (int, float)}
_EPHEMERAL = discord.MessageFlags(ephemeral=True).value


def _to_message(env: Env, payload: dict[str, Any]) -> discord.Message:
    state = env.bot._connection
    channel = env.bot.get_channel(int(payload["channel_id"]))
    return discord.Message(state=state, channel=channel, data=payload)  # type: ignore[arg-type]


class UserHandle:
    """A virtual human user (not yet in any guild)."""

    def __init__(self, env: Env, payload: dict[str, Any]) -> None:
        self._env = env
        self.payload = payload

    @property
    def id(self) -> int:
        return int(self.payload["id"])

    @property
    def name(self) -> str:
        return self.payload["username"]

    @property
    def mention(self) -> str:
        return f"<@{self.id}>"


class RoleHandle:
    def __init__(self, env: Env, guild: GuildHandle, payload: dict[str, Any]) -> None:
        self._env = env
        self.guild = guild
        self.payload = payload

    @property
    def id(self) -> int:
        return int(self.payload["id"])

    @property
    def name(self) -> str:
        return self.payload["name"]


class GuildHandle:
    def __init__(self, env: Env, data: dict[str, Any]) -> None:
        self._env = env
        self._data = data

    @property
    def id(self) -> int:
        return int(self._data["id"])

    @property
    def default_role(self) -> RoleHandle:
        return RoleHandle(self._env, self, self._data["roles"][self.id])

    @property
    def me(self) -> Optional[discord.Member]:
        guild = self._env.bot.get_guild(self.id)
        return guild.me if guild else None

    @property
    def channels(self) -> dict[str, ChannelHandle]:
        backend = self._env.backend
        return {
            backend.channels[cid]["name"]: ChannelHandle(self._env, self, backend.channels[cid])
            for cid in self._data["channel_ids"]
        }

    def create_text_channel(
        self,
        name: str,
        *,
        overwrites: Optional[dict[Union[RoleHandle, "MemberActor"], discord.PermissionOverwrite]] = None,
    ) -> ChannelHandle:
        ow_payloads = []
        for target, overwrite in (overwrites or {}).items():
            allow, deny = overwrite.pair()
            ow_payloads.append(
                {
                    "id": str(target.id),
                    "type": 0 if isinstance(target, RoleHandle) else 1,
                    "allow": str(allow.value),
                    "deny": str(deny.value),
                }
            )
        payload = self._env.backend.create_channel(self.id, name, overwrites=ow_payloads)
        return ChannelHandle(self._env, self, payload)

    def create_role(self, name: str, *, permissions: Optional[discord.Permissions] = None, **fields: Any) -> RoleHandle:
        payload = self._env.backend.create_role(
            self.id, name, permissions=permissions.value if permissions else 0, **fields
        )
        return RoleHandle(self._env, self, payload)

    def add_member(
        self,
        user: UserHandle,
        *,
        roles: Sequence[RoleHandle] = (),
        nick: Optional[str] = None,
    ) -> MemberActor:
        self._env.backend.add_member(
            self.id, user.id, roles=[r.id for r in roles], nick=nick, announce=True
        )
        return MemberActor(self._env, self, user)

    def get_ban(self, user: Union[UserHandle, MemberActor]) -> Optional[dict[str, Any]]:
        return self._data["bans"].get(user.id)

    def member_ids(self) -> list[int]:
        return list(self._data["members"])


class ChannelHandle:
    def __init__(self, env: Env, guild: Optional[GuildHandle], payload: dict[str, Any]) -> None:
        self._env = env
        self.guild = guild
        self.payload = payload

    @property
    def id(self) -> int:
        return int(self.payload["id"])

    @property
    def name(self) -> str:
        return self.payload["name"]

    @property
    def mention(self) -> str:
        return f"<#{self.id}>"

    def history(self, *, viewer: Optional[MemberActor] = None) -> list[discord.Message]:
        """All messages in the channel, oldest first, as real discord.Message objects.

        With ``viewer=``, ephemeral messages not addressed to that user are hidden.
        """
        out = []
        for payload in sorted(self._env.backend.messages[self.id].values(), key=lambda m: int(m["id"])):
            if int(payload.get("flags") or 0) & _EPHEMERAL:
                meta = payload.get("interaction_metadata") or {}
                if viewer is None or str(viewer.id) != str(meta.get("user", {}).get("id")):
                    continue
            out.append(_to_message(self._env, payload))
        return out

    @property
    def last_message(self) -> Optional[discord.Message]:
        history = self.history()
        return history[-1] if history else None


class MemberActor:
    """A guild member that acts like a real human user would."""

    def __init__(self, env: Env, guild: GuildHandle, user: UserHandle) -> None:
        self._env = env
        self.guild = guild
        self.user = user

    @property
    def id(self) -> int:
        return self.user.id

    @property
    def mention(self) -> str:
        return self.user.mention

    @property
    def member(self) -> Optional[discord.Member]:
        guild = self._env.bot.get_guild(self.guild.id)
        return guild.get_member(self.id) if guild else None

    def _check(self, channel: ChannelHandle, *permissions: str) -> None:
        self._env.backend.require_permissions(self.guild.id, self.id, channel.id, *permissions)

    # ----------------------------------------------------------------- text

    async def send(
        self,
        channel: ChannelHandle,
        content: str = "",
        *,
        reply_to: Optional[discord.Message] = None,
    ) -> discord.Message:
        self._check(channel, "send_messages")
        reference = None
        if reply_to is not None:
            reference = {"channel_id": str(reply_to.channel.id), "message_id": str(reply_to.id)}
        payload = self._env.backend.create_message(
            channel.id, self.id, content, message_reference=reference
        )
        await self._env.settle()
        return _to_message(self._env, payload)

    # ----------------------------------------------------------- interactions

    def _base_interaction(self, type: int, channel: ChannelHandle, data: dict[str, Any]) -> dict[str, Any]:
        backend = self._env.backend
        record = backend.new_interaction(type, channel.id, self.id, self.guild.id)
        member = backend.member_payload(self.guild.id, self.id)
        member["permissions"] = str(backend.compute_permissions(self.guild.id, self.id, channel.id))
        payload = {
            "id": str(record["id"]),
            "application_id": str(backend.application_id),
            "type": type,
            "token": record["token"],
            "version": 1,
            "data": data,
            "guild_id": str(self.guild.id),
            "channel_id": str(channel.id),
            "channel": dict(channel.payload),
            "member": member,
            "locale": "en-US",
            "guild_locale": "en-US",
            "app_permissions": str(
                backend.compute_permissions(self.guild.id, int(backend.bot_user["id"]), channel.id)
            ),
            "entitlements": [],
            "authorizing_integration_owners": {},
            "context": 0,
            "attachment_size_limit": 26214400,
        }
        record["payload"] = payload
        return payload

    def _build_options(self, command: dict[str, Any], options: dict[str, Any]) -> tuple[list, dict]:
        built: list[dict[str, Any]] = []
        resolved: dict[str, dict[str, Any]] = {}
        backend = self._env.backend
        declared = {o["name"]: o for o in command.get("options") or []}
        for name, value in options.items():
            spec = declared.get(name)
            if spec is None:
                raise SetupError(
                    f"Command '{command['name']}' has no option '{name}' "
                    f"(declared: {sorted(declared)})"
                )
            opt_type = spec["type"]
            if opt_type in (6, 7, 8, 9):  # user / channel / role / mentionable
                wire_value = str(value.id)
                if opt_type in (6, 9) and isinstance(value, (MemberActor, UserHandle)):
                    resolved.setdefault("users", {})[wire_value] = backend.users[value.id]
                    if isinstance(value, MemberActor):
                        resolved.setdefault("members", {})[wire_value] = backend.member_payload(
                            self.guild.id, value.id, with_user=False
                        )
                elif opt_type == 7 and isinstance(value, ChannelHandle):
                    resolved.setdefault("channels", {})[wire_value] = dict(value.payload)
                elif opt_type == 8 and isinstance(value, RoleHandle):
                    resolved.setdefault("roles", {})[wire_value] = dict(value.payload)
            else:
                expected = _OPTION_TYPES.get(opt_type)
                if expected is not None and not isinstance(value, expected):
                    raise SetupError(f"Option '{name}' expects {expected}, got {type(value).__name__}")
                wire_value = value
            built.append({"name": name, "type": opt_type, "value": wire_value})
        for name, spec in declared.items():
            if spec.get("required") and name not in options:
                raise SetupError(f"Command '{command['name']}' requires option '{name}'")
        return built, resolved

    def _find_command(self, name: str, type: int = 1) -> dict[str, Any]:
        backend = self._env.backend
        command = backend.find_command(name, self.guild.id, type=type)
        if command is None:
            tree = getattr(self._env.bot, "tree", None)
            in_tree = tree is not None and any(
                c.name == name for c in tree.get_commands() + tree.get_commands(guild=discord.Object(self.guild.id))
            )
            if in_tree and self._env.strict_sync:
                raise SetupError(
                    f"Command '{name}' exists in the command tree but was never synced — "
                    "did you forget `await bot.tree.sync()`? "
                    "(Pass strict_sync=False to dpt.run to auto-allow unsynced commands.)"
                )
            if in_tree and tree is not None:
                cmd = discord.utils.get(tree.get_commands(), name=name) or discord.utils.get(
                    tree.get_commands(guild=discord.Object(self.guild.id)), name=name
                )
                return self._env.backend.register_commands(None, [cmd.to_dict(tree)])[0]  # type: ignore[union-attr]
            raise SetupError(f"No application command named '{name}' exists")
        return command

    async def slash(self, channel: ChannelHandle, name: str, **options: Any) -> InteractionResult:
        """Invoke a synced slash command as this user."""
        self._check(channel, "use_application_commands")
        command = self._find_command(name)
        opts, resolved = self._build_options(command, options)
        data: dict[str, Any] = {
            "id": command["id"],
            "name": command["name"],
            "type": command.get("type", 1),
            "options": opts,
        }
        if resolved:
            data["resolved"] = resolved
        if command.get("guild_id"):
            data["guild_id"] = command["guild_id"]
        payload = self._base_interaction(2, channel, data)
        record = self._env.backend.interactions[int(payload["id"])]
        self._env.backend.emit("INTERACTION_CREATE", payload)
        await self._env.settle()
        return InteractionResult(self._env, record)

    def _message_payload(self, message: Union[discord.Message, dict[str, Any]]) -> dict[str, Any]:
        if isinstance(message, discord.Message):
            return self._env.backend.get_message(message.channel.id, message.id)
        return message

    async def _component_interaction(
        self, message_payload: dict[str, Any], data: dict[str, Any]
    ) -> InteractionResult:
        channel = ChannelHandle(
            self._env, self.guild, self._env.backend.get_channel(int(message_payload["channel_id"]))
        )
        payload = self._base_interaction(3, channel, data)
        payload["message"] = dict(message_payload)
        record = self._env.backend.interactions[int(payload["id"])]
        record["source_message_id"] = int(message_payload["id"])
        self._env.backend.emit("INTERACTION_CREATE", payload)
        await self._env.settle()
        return InteractionResult(self._env, record)

    def _find_component(
        self, message_payload: dict[str, Any], *, types: tuple[int, ...], custom_id: Optional[str], label: Optional[str]
    ) -> dict[str, Any]:
        found = []
        for row in message_payload.get("components") or []:
            for component in row.get("components") or []:
                if component.get("type") not in types:
                    continue
                if custom_id is not None and component.get("custom_id") != custom_id:
                    continue
                if label is not None and component.get("label") != label:
                    continue
                found.append(component)
        if not found:
            raise SetupError(
                f"No matching component on message {message_payload['id']} "
                f"(custom_id={custom_id!r}, label={label!r}) — a real user could not interact with it"
            )
        component = found[0]
        if component.get("disabled"):
            raise SetupError("That component is disabled — a real user could not interact with it")
        return component

    async def click(
        self,
        message: Union[discord.Message, dict[str, Any]],
        *,
        label: Optional[str] = None,
        custom_id: Optional[str] = None,
    ) -> InteractionResult:
        """Click a button on a message, exactly as a user could."""
        payload = self._message_payload(message)
        button = self._find_component(payload, types=(2,), custom_id=custom_id, label=label)
        return await self._component_interaction(
            payload, {"custom_id": button["custom_id"], "component_type": 2}
        )

    async def select(
        self,
        message: Union[discord.Message, dict[str, Any]],
        values: Sequence[str],
        *,
        custom_id: Optional[str] = None,
    ) -> InteractionResult:
        """Choose values in a string select menu."""
        payload = self._message_payload(message)
        menu = self._find_component(payload, types=(3,), custom_id=custom_id, label=None)
        valid = {o["value"] for o in menu.get("options") or []}
        for value in values:
            if value not in valid:
                raise SetupError(f"Select option {value!r} does not exist (options: {sorted(valid)})")
        return await self._component_interaction(
            payload,
            {"custom_id": menu["custom_id"], "component_type": 3, "values": list(values)},
        )

    async def submit_modal(self, modal: InteractionResult, values: dict[str, str]) -> InteractionResult:
        """Fill in and submit a modal previously returned to this user."""
        spec = modal.modal
        if spec is None:
            raise SetupError("That interaction did not respond with a modal")
        components = []
        for row in spec.get("components") or []:
            for item in row.get("components") or []:
                if item.get("custom_id") in values:
                    components.append(
                        {
                            "type": 1,
                            "components": [
                                {"type": 4, "custom_id": item["custom_id"], "value": values[item["custom_id"]]}
                            ],
                        }
                    )
        channel = ChannelHandle(
            self._env, self.guild, self._env.backend.get_channel(modal.record["channel_id"])
        )
        payload = self._base_interaction(
            5, channel, {"custom_id": spec["custom_id"], "components": components}
        )
        record = self._env.backend.interactions[int(payload["id"])]
        self._env.backend.emit("INTERACTION_CREATE", payload)
        await self._env.settle()
        return InteractionResult(self._env, record)


class ResponseMessage:
    """A message the bot sent in response to an interaction."""

    def __init__(self, env: Env, payload: dict[str, Any]) -> None:
        self._env = env
        self.payload = payload

    @property
    def id(self) -> int:
        return int(self.payload["id"])

    @property
    def content(self) -> str:
        return self.payload["content"]

    @property
    def embeds(self) -> list[discord.Embed]:
        return [discord.Embed.from_dict(e) for e in self.payload["embeds"]]

    @property
    def ephemeral(self) -> bool:
        return bool(int(self.payload.get("flags") or 0) & _EPHEMERAL)

    @property
    def message(self) -> discord.Message:
        return _to_message(self._env, self.payload)


class InteractionResult:
    """What happened in response to a simulated interaction."""

    def __init__(self, env: Env, record: dict[str, Any]) -> None:
        self._env = env
        self.record = record

    @property
    def acknowledged(self) -> bool:
        return self.record["responded"]

    @property
    def deferred(self) -> bool:
        return self.record["response_kind"] == "deferred"

    @property
    def ephemeral(self) -> bool:
        return self.record["ephemeral"]

    @property
    def modal(self) -> Optional[dict[str, Any]]:
        return self.record["modal"]

    @property
    def autocomplete_choices(self) -> Optional[list[dict[str, Any]]]:
        return self.record["autocomplete_choices"]

    @property
    def response(self) -> Optional[ResponseMessage]:
        if self.record["message_id"] is None:
            return None
        payload = self._env.backend.get_message(self.record["channel_id"], self.record["message_id"])
        return ResponseMessage(self._env, payload)

    @property
    def followups(self) -> list[ResponseMessage]:
        return [
            ResponseMessage(self._env, self._env.backend.get_message(self.record["channel_id"], mid))
            for mid in self.record["followup_ids"]
        ]
