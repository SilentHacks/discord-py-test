"""Application/user-level routes: identity, application info, DM channels."""

from __future__ import annotations

from typing import Any

from ...backend import errors, serializers
from ..router import RequestContext, route


@route("GET", "/users/@me")
def me(ctx: RequestContext) -> Any:
    return dict(serializers.user_payload(ctx.backend.bot_user))


@route("GET", "/users/{user_id}")
def get_user(ctx: RequestContext) -> Any:
    return dict(serializers.user_payload(ctx.backend.get_user(ctx.int_arg("user_id"))))


@route("GET", "/oauth2/applications/@me")
def application_info(ctx: RequestContext) -> Any:
    backend = ctx.backend
    bot = dict(serializers.user_payload(backend.bot_user))
    return {
        "id": str(backend.application_id),
        "name": backend.bot_user.name,
        "icon": None,
        "description": "",
        "summary": "",
        "bot_public": True,
        "bot_require_code_grant": False,
        "verify_key": "0" * 64,
        "owner": bot,
        "flags": 0,
        "team": None,
        "bot": bot,
    }


@route("POST", "/users/@me/channels")
def create_dm(ctx: RequestContext) -> Any:
    recipient_id = int(ctx.body()["recipient_id"])
    recipient = ctx.backend.get_user(recipient_id)
    if recipient.bot:
        raise errors.cannot_dm_bot()
    channel = ctx.backend.get_dm_channel(recipient_id)
    return dict(serializers.channel_payload(ctx.backend, channel))
