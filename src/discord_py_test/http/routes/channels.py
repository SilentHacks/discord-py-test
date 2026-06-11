"""Channel routes: fetch/edit/delete, typing, overwrites, threads, webhooks."""

from __future__ import annotations

from typing import Any

from ...backend import serializers
from ...backend.models import Overwrite
from ..router import RequestContext, route


@route("GET", "/channels/{channel_id}")
def get_channel(ctx: RequestContext) -> Any:
    return dict(serializers.channel_payload(ctx.backend, ctx.backend.get_channel(ctx.int_arg("channel_id"))))


@route("PATCH", "/channels/{channel_id}")
def edit_channel(ctx: RequestContext) -> Any:
    backend = ctx.backend
    channel = backend.get_channel(ctx.int_arg("channel_id"))
    backend.require_permissions(channel.guild_id, backend.bot_user.id, channel.id, "manage_channels")
    body = ctx.body()
    for key in ("name", "topic", "nsfw", "rate_limit_per_user"):
        if key in body:
            setattr(channel, key, body[key])
    if "permission_overwrites" in body:
        channel.overwrites = [
            Overwrite(target_id=int(o["id"]), type=int(o["type"]), allow=int(o.get("allow", 0)), deny=int(o.get("deny", 0)))
            for o in body["permission_overwrites"]
        ]
    backend.announce_channel_update(channel.id)
    return dict(serializers.channel_payload(backend, channel))


@route("DELETE", "/channels/{channel_id}")
def delete_channel(ctx: RequestContext) -> Any:
    backend = ctx.backend
    channel = backend.get_channel(ctx.int_arg("channel_id"))
    backend.require_permissions(channel.guild_id, backend.bot_user.id, channel.id, "manage_channels")
    payload = dict(serializers.channel_payload(backend, channel))
    backend.delete_channel(channel.id)
    return payload


@route("PUT", "/channels/{channel_id}/permissions/{target_id}")
def edit_overwrite(ctx: RequestContext) -> Any:
    backend = ctx.backend
    channel = backend.get_channel(ctx.int_arg("channel_id"))
    backend.require_permissions(channel.guild_id, backend.bot_user.id, channel.id, "manage_roles")
    body = ctx.body()
    target_id = ctx.int_arg("target_id")
    channel.overwrites = [o for o in channel.overwrites if o.target_id != target_id]
    channel.overwrites.append(
        Overwrite(
            target_id=target_id,
            type=int(body["type"]),
            allow=int(body.get("allow", 0)),
            deny=int(body.get("deny", 0)),
        )
    )
    backend.announce_channel_update(channel.id)


@route("DELETE", "/channels/{channel_id}/permissions/{target_id}")
def delete_overwrite(ctx: RequestContext) -> Any:
    backend = ctx.backend
    channel = backend.get_channel(ctx.int_arg("channel_id"))
    backend.require_permissions(channel.guild_id, backend.bot_user.id, channel.id, "manage_roles")
    target_id = ctx.int_arg("target_id")
    channel.overwrites = [o for o in channel.overwrites if o.target_id != target_id]
    backend.announce_channel_update(channel.id)


@route("POST", "/channels/{channel_id}/typing")
def typing(ctx: RequestContext) -> Any:
    backend = ctx.backend
    channel = backend.get_channel(ctx.int_arg("channel_id"))
    payload: dict[str, Any] = {
        "channel_id": str(channel.id),
        "user_id": str(backend.bot_user.id),
        "timestamp": 0,
    }
    if channel.guild_id is not None:
        payload["guild_id"] = str(channel.guild_id)
    backend.emit("TYPING_START", payload)


@route("POST", "/channels/{channel_id}/threads")
def create_thread(ctx: RequestContext) -> Any:
    backend = ctx.backend
    channel = backend.get_channel(ctx.int_arg("channel_id"))
    body = ctx.body()
    backend.require_permissions(channel.guild_id, backend.bot_user.id, channel.id, "create_public_threads")
    thread = backend.create_thread(
        channel.id,
        body["name"],
        backend.bot_user.id,
        type=int(body.get("type", 11)),
        auto_archive_duration=int(body.get("auto_archive_duration", 1440)),
    )
    return dict(serializers.thread_payload(backend, thread))


@route("POST", "/channels/{channel_id}/messages/{message_id}/threads")
def create_thread_from_message(ctx: RequestContext) -> Any:
    backend = ctx.backend
    channel = backend.get_channel(ctx.int_arg("channel_id"))
    message = backend.get_message(channel.id, ctx.int_arg("message_id"))
    body = ctx.body()
    backend.require_permissions(channel.guild_id, backend.bot_user.id, channel.id, "create_public_threads")
    thread = backend.create_thread(
        channel.id,
        body["name"],
        backend.bot_user.id,
        message_id=message.id,
        auto_archive_duration=int(body.get("auto_archive_duration", 1440)),
    )
    return dict(serializers.thread_payload(backend, thread))


@route("POST", "/channels/{channel_id}/webhooks")
def create_webhook(ctx: RequestContext) -> Any:
    backend = ctx.backend
    channel = backend.get_channel(ctx.int_arg("channel_id"))
    backend.require_permissions(channel.guild_id, backend.bot_user.id, channel.id, "manage_webhooks")
    webhook = backend.create_webhook(channel.id, ctx.body().get("name") or "Webhook", backend.bot_user.id)
    return serializers.webhook_payload(backend, webhook)


@route("GET", "/channels/{channel_id}/webhooks")
def get_channel_webhooks(ctx: RequestContext) -> Any:
    backend = ctx.backend
    channel_id = ctx.int_arg("channel_id")
    backend.get_channel(channel_id)
    return [
        serializers.webhook_payload(backend, w)
        for w in backend.webhooks.values()
        if w.channel_id == channel_id
    ]
