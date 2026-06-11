"""REST route handlers over the virtual backend.

Every REST call discord.py makes (via ``HTTPClient.request`` or the webhook
adapter) is matched against this table. Unknown routes fail loudly with
:class:`~discord_py_test.errors.RouteNotImplemented` — the backend never
silently fakes success.
"""

from __future__ import annotations

import json as _json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import discord

from . import errors
from .backend import Backend

EPHEMERAL = discord.MessageFlags(ephemeral=True).value


@dataclass
class RequestContext:
    backend: Backend
    args: dict[str, str]
    json: Optional[dict[str, Any]] = None
    params: dict[str, Any] = field(default_factory=dict)
    files: list[Any] = field(default_factory=list)


Handler = Callable[[RequestContext], Any]
_ROUTES: dict[str, list[tuple[list[str], Handler]]] = {}


def route(method: str, template: str) -> Callable[[Handler], Handler]:
    def decorator(func: Handler) -> Handler:
        _ROUTES.setdefault(method, []).append((template.strip("/").split("/"), func))
        return func

    return decorator


def dispatch(
    backend: Backend,
    method: str,
    path: str,
    *,
    json: Optional[dict[str, Any]] = None,
    params: Optional[dict[str, Any]] = None,
    files: Optional[list[Any]] = None,
) -> Any:
    segments = path.strip("/").split("/")
    for template, handler in _ROUTES.get(method, ()):
        if len(template) != len(segments):
            continue
        args: dict[str, str] = {}
        for tpl, seg in zip(template, segments):
            if tpl.startswith("{") and tpl.endswith("}"):
                args[tpl[1:-1]] = seg
            elif tpl != seg:
                break
        else:
            ctx = RequestContext(backend, args, json=json, params=params or {}, files=files or [])
            return handler(ctx)
    raise errors.RouteNotImplemented(method, path)


def _store_files(ctx: RequestContext, channel_id: int) -> list[dict[str, Any]]:
    attachments = []
    for f in ctx.files:
        data = f.fp.read()
        attachments.append(ctx.backend.store_attachment(channel_id, f.filename, data, f.description))
    return attachments


def _bot_message(ctx: RequestContext, channel_id: int, *, interaction: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Create a message authored by the bot from a request body."""
    backend = ctx.backend
    body = ctx.json or {}
    flags = int(body.get("flags") or 0)
    ephemeral = bool(flags & EPHEMERAL)
    interaction_metadata = None
    if interaction is not None:
        interaction_metadata = {
            "id": str(interaction["id"]),
            "type": interaction["type"],
            "user": backend.users[interaction["user_id"]],
            "authorizing_integration_owners": {},
        }
    reference = body.get("message_reference")
    if reference:
        reference = {
            "channel_id": str(reference.get("channel_id", channel_id)),
            "message_id": str(reference["message_id"]),
        }
    return backend.create_message(
        channel_id,
        int(backend.bot_user["id"]),
        body.get("content") or "",
        embeds=body.get("embeds") or ([body["embed"]] if body.get("embed") else []),
        components=body.get("components") or [],
        attachments=_store_files(ctx, channel_id),
        flags=flags,
        message_reference=reference,
        interaction_metadata=interaction_metadata,
        broadcast=not ephemeral,
    )


# ---------------------------------------------------------------- messages


@route("POST", "/channels/{channel_id}/messages")
def send_message(ctx: RequestContext) -> Any:
    backend = ctx.backend
    channel_id = int(ctx.args["channel_id"])
    channel = backend.get_channel(channel_id)
    guild_id = int(channel["guild_id"]) if channel.get("guild_id") else None
    backend.require_permissions(guild_id, int(backend.bot_user["id"]), channel_id, "send_messages")
    return _bot_message(ctx, channel_id)


@route("GET", "/channels/{channel_id}/messages/{message_id}")
def get_message(ctx: RequestContext) -> Any:
    return ctx.backend.get_message(int(ctx.args["channel_id"]), int(ctx.args["message_id"]))


@route("GET", "/channels/{channel_id}/messages")
def get_messages(ctx: RequestContext) -> Any:
    channel_id = int(ctx.args["channel_id"])
    ctx.backend.get_channel(channel_id)
    limit = int(ctx.params.get("limit", 50))
    messages = sorted(ctx.backend.messages[channel_id].values(), key=lambda m: int(m["id"]), reverse=True)
    return messages[:limit]


@route("PATCH", "/channels/{channel_id}/messages/{message_id}")
def edit_message(ctx: RequestContext) -> Any:
    return ctx.backend.edit_message(int(ctx.args["channel_id"]), int(ctx.args["message_id"]), ctx.json or {})


@route("DELETE", "/channels/{channel_id}/messages/{message_id}")
def delete_message(ctx: RequestContext) -> Any:
    backend = ctx.backend
    channel_id = int(ctx.args["channel_id"])
    message = backend.get_message(channel_id, int(ctx.args["message_id"]))
    channel = backend.get_channel(channel_id)
    if int(message["author"]["id"]) != int(backend.bot_user["id"]) and channel.get("guild_id"):
        backend.require_permissions(int(channel["guild_id"]), int(backend.bot_user["id"]), channel_id, "manage_messages")
    backend.delete_message(channel_id, int(ctx.args["message_id"]))


@route("POST", "/channels/{channel_id}/typing")
def typing(ctx: RequestContext) -> Any:
    backend = ctx.backend
    channel = backend.get_channel(int(ctx.args["channel_id"]))
    payload: dict[str, Any] = {
        "channel_id": channel["id"],
        "user_id": backend.bot_user["id"],
        "timestamp": 0,
    }
    if channel.get("guild_id"):
        payload["guild_id"] = channel["guild_id"]
    backend.emit("TYPING_START", payload)


@route("GET", "/channels/{channel_id}")
def get_channel(ctx: RequestContext) -> Any:
    return ctx.backend.get_channel(int(ctx.args["channel_id"]))


@route("GET", "/oauth2/applications/@me")
def application_info(ctx: RequestContext) -> Any:
    backend = ctx.backend
    return {
        "id": str(backend.application_id),
        "name": backend.bot_user["username"],
        "icon": None,
        "description": "",
        "summary": "",
        "bot_public": True,
        "bot_require_code_grant": False,
        "verify_key": "0" * 64,
        "owner": backend.bot_user,
        "flags": 0,
        "team": None,
        "bot": backend.bot_user,
    }


@route("GET", "/users/@me")
def me(ctx: RequestContext) -> Any:
    return dict(ctx.backend.bot_user)


# ------------------------------------------------------------------ guilds


@route("DELETE", "/guilds/{guild_id}/members/{user_id}")
def kick(ctx: RequestContext) -> Any:
    backend = ctx.backend
    guild_id = int(ctx.args["guild_id"])
    backend.require_permissions(guild_id, int(backend.bot_user["id"]), None, "kick_members")
    backend.remove_member(guild_id, int(ctx.args["user_id"]))


@route("PUT", "/guilds/{guild_id}/bans/{user_id}")
def ban(ctx: RequestContext) -> Any:
    backend = ctx.backend
    guild_id = int(ctx.args["guild_id"])
    user_id = int(ctx.args["user_id"])
    backend.require_permissions(guild_id, int(backend.bot_user["id"]), None, "ban_members")
    guild = backend.get_guild(guild_id)
    guild["bans"][user_id] = {"user": backend.users[user_id], "reason": None}
    if user_id in guild["members"]:
        backend.remove_member(guild_id, user_id)
    backend.emit("GUILD_BAN_ADD", {"guild_id": guild["id"], "user": backend.users[user_id]})


@route("DELETE", "/guilds/{guild_id}/bans/{user_id}")
def unban(ctx: RequestContext) -> Any:
    backend = ctx.backend
    guild_id = int(ctx.args["guild_id"])
    user_id = int(ctx.args["user_id"])
    backend.require_permissions(guild_id, int(backend.bot_user["id"]), None, "ban_members")
    guild = backend.get_guild(guild_id)
    if user_id not in guild["bans"]:
        raise errors.unknown("Ban", 10026)
    del guild["bans"][user_id]
    backend.emit("GUILD_BAN_REMOVE", {"guild_id": guild["id"], "user": backend.users[user_id]})


# --------------------------------------------------- application commands


@route("PUT", "/applications/{application_id}/commands")
def bulk_upsert_global_commands(ctx: RequestContext) -> Any:
    return ctx.backend.register_commands(None, ctx.json or [])  # type: ignore[arg-type]


@route("PUT", "/applications/{application_id}/guilds/{guild_id}/commands")
def bulk_upsert_guild_commands(ctx: RequestContext) -> Any:
    return ctx.backend.register_commands(int(ctx.args["guild_id"]), ctx.json or [])  # type: ignore[arg-type]


@route("GET", "/applications/{application_id}/commands")
def get_global_commands(ctx: RequestContext) -> Any:
    return list(ctx.backend.commands.get(None, {}).values())


@route("GET", "/applications/{application_id}/guilds/{guild_id}/commands")
def get_guild_commands(ctx: RequestContext) -> Any:
    return list(ctx.backend.commands.get(int(ctx.args["guild_id"]), {}).values())


# ----------------------------------------------------------- interactions


@route("POST", "/interactions/{interaction_id}/{token}/callback")
def interaction_callback(ctx: RequestContext) -> Any:
    backend = ctx.backend
    record = backend.interaction_by_token(ctx.args["token"])
    if record["responded"]:
        raise errors.already_acknowledged()
    body = ctx.json or {}
    cb_type = body["type"]
    data = body.get("data") or {}
    record["responded"] = True
    message = None

    if cb_type == 4:  # channel message with source
        ctx.json = data
        record["ephemeral"] = bool(int(data.get("flags") or 0) & EPHEMERAL)
        message = _bot_message(ctx, record["channel_id"], interaction=record)
        record["response_kind"] = "message"
        record["message_id"] = int(message["id"])
    elif cb_type in (5, 6):  # deferred
        record["response_kind"] = "deferred"
        record["ephemeral"] = bool(int(data.get("flags") or 0) & EPHEMERAL)
    elif cb_type == 7:  # update message (components)
        record["response_kind"] = "update"
        if record["source_message_id"] is not None:
            message = backend.edit_message(record["channel_id"], record["source_message_id"], data)
            record["message_id"] = record["source_message_id"]
    elif cb_type == 9:  # modal
        record["response_kind"] = "modal"
        record["modal"] = data
    elif cb_type == 8:  # autocomplete result
        record["response_kind"] = "autocomplete"
        record["autocomplete_choices"] = data.get("choices", [])
    elif cb_type == 1:  # pong
        record["response_kind"] = "pong"
    else:
        raise errors.BackendError(400, 50035, f"Unknown interaction callback type {cb_type}")

    response: dict[str, Any] = {
        "interaction": {
            "id": str(record["id"]),
            "type": record["type"],
            "activity_instance_id": None,
            "response_message_id": str(record["message_id"]) if record["message_id"] else None,
            "response_message_loading": record["response_kind"] == "deferred",
            "response_message_ephemeral": record["ephemeral"],
        }
    }
    if message is not None:
        response["resource"] = {"type": cb_type, "message": message}
    return response


def _interaction_for_webhook(ctx: RequestContext) -> dict[str, Any]:
    return ctx.backend.interaction_by_token(ctx.args["token"])


@route("POST", "/webhooks/{application_id}/{token}")
def interaction_followup(ctx: RequestContext) -> Any:
    record = _interaction_for_webhook(ctx)
    message = _bot_message(ctx, record["channel_id"], interaction=record)
    record["followup_ids"].append(int(message["id"]))
    return message


@route("GET", "/webhooks/{application_id}/{token}/messages/@original")
def get_original_response(ctx: RequestContext) -> Any:
    record = _interaction_for_webhook(ctx)
    if record["message_id"] is None:
        raise errors.unknown("Message", 10008)
    return ctx.backend.get_message(record["channel_id"], record["message_id"])


@route("PATCH", "/webhooks/{application_id}/{token}/messages/@original")
def edit_original_response(ctx: RequestContext) -> Any:
    record = _interaction_for_webhook(ctx)
    backend = ctx.backend
    body = dict(ctx.json or {})
    if record["message_id"] is None and record["response_kind"] == "deferred":
        # Editing a deferred response materialises the followup message.
        ctx.json = body
        flags = EPHEMERAL if record["ephemeral"] else 0
        body["flags"] = int(body.get("flags") or 0) | flags
        message = _bot_message(ctx, record["channel_id"], interaction=record)
        record["message_id"] = int(message["id"])
        record["response_kind"] = "message"
        return message
    return backend.edit_message(record["channel_id"], record["message_id"], body)


@route("DELETE", "/webhooks/{application_id}/{token}/messages/@original")
def delete_original_response(ctx: RequestContext) -> Any:
    record = _interaction_for_webhook(ctx)
    if record["message_id"] is not None:
        ctx.backend.delete_message(record["channel_id"], record["message_id"])
        record["message_id"] = None


@route("PATCH", "/webhooks/{application_id}/{token}/messages/{message_id}")
def edit_followup(ctx: RequestContext) -> Any:
    record = _interaction_for_webhook(ctx)
    return ctx.backend.edit_message(record["channel_id"], int(ctx.args["message_id"]), ctx.json or {})


@route("DELETE", "/webhooks/{application_id}/{token}/messages/{message_id}")
def delete_followup(ctx: RequestContext) -> Any:
    record = _interaction_for_webhook(ctx)
    ctx.backend.delete_message(record["channel_id"], int(ctx.args["message_id"]))


def parse_form(form: list[dict[str, Any]], files: list[Any]) -> tuple[Optional[dict[str, Any]], list[Any]]:
    """Extract the JSON payload from a multipart form built by discord.py."""
    payload = None
    for part in form:
        if part.get("name") == "payload_json":
            payload = _json.loads(part["value"])
    return payload, list(files or [])
