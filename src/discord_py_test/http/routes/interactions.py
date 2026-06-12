"""Interaction lifecycle routes: callback, followups, original-response ops.

The webhook execute route is shared with standalone channel webhooks: tokens
are looked up first as interaction tokens, then as webhook tokens.
"""

from __future__ import annotations

from typing import Any

from ...backend import errors
from ...backend.models import EPHEMERAL_FLAG
from .._helpers import bot_message, message_response
from ..router import RequestContext, route


@route("POST", "/interactions/{interaction_id}/{token}/callback")
def interaction_callback(ctx: RequestContext) -> Any:
    backend = ctx.backend
    record = backend.interaction_by_token(ctx.args["token"])
    if record["responded"]:
        raise errors.already_acknowledged()
    body = ctx.body()
    callback_type = body["type"]
    data = body.get("data") or {}
    ephemeral = bool(int(data.get("flags") or 0) & EPHEMERAL_FLAG)
    message = None

    # Don't mark the interaction acknowledged until the callback is handled
    # successfully: a callback that 400s (e.g. an oversized embed) does not
    # consume the interaction on real Discord, so a retry must not see 40060.
    if callback_type == 4:  # channel message with source
        message = bot_message(ctx, record["channel_id"], interaction=record, body=data)
        record["response_kind"] = "message"
        record["message_id"] = message.id
        record["ephemeral"] = ephemeral
    elif callback_type == 5:  # deferred channel message with source
        record["response_kind"] = "deferred"
        record["ephemeral"] = ephemeral
    elif callback_type == 6:  # deferred update of the component's message
        # @original is the clicked message; a later edit_original_response edits
        # it in place rather than creating a new message.
        record["response_kind"] = "deferred_update"
        record["message_id"] = record["source_message_id"]
    elif callback_type == 7:  # update the component's message
        record["response_kind"] = "update"
        if record["source_message_id"] is not None:
            message = backend.edit_message(record["channel_id"], record["source_message_id"], data)
            record["message_id"] = record["source_message_id"]
    elif callback_type == 9:  # modal
        record["response_kind"] = "modal"
        record["modal"] = data
    elif callback_type == 8:  # autocomplete result
        record["response_kind"] = "autocomplete"
        record["autocomplete_choices"] = data.get("choices", [])
    elif callback_type == 1:  # pong
        record["response_kind"] = "pong"
    else:
        raise errors.invalid_form_body(f"unknown interaction callback type {callback_type}")

    record["responded"] = True

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
        response["resource"] = {"type": callback_type, "message": message_response(ctx, message)}
    return response


@route("POST", "/webhooks/{webhook_id}/{token}")
def execute_webhook(ctx: RequestContext) -> Any:
    backend = ctx.backend
    token = ctx.args["token"]
    if token in backend.interaction_tokens:
        record = backend.interaction_by_token(token)
        message = bot_message(ctx, record["channel_id"], interaction=record)
        record["followup_ids"].append(message.id)
        return message_response(ctx, message)
    webhook_id = backend.webhook_tokens.get(token)
    if webhook_id is None or backend.webhooks[webhook_id].id != ctx.int_arg("webhook_id"):
        raise errors.unknown_webhook()
    webhook = backend.webhooks[webhook_id]
    message = bot_message(ctx, webhook.channel_id, author_id=webhook.webhook_user_id, webhook_id=webhook.id)
    return message_response(ctx, message)


def _record(ctx: RequestContext) -> dict[str, Any]:
    return ctx.backend.interaction_by_token(ctx.args["token"])


@route("GET", "/webhooks/{webhook_id}/{token}/messages/@original")
def get_original_response(ctx: RequestContext) -> Any:
    record = _record(ctx)
    if record["message_id"] is None:
        raise errors.unknown_message()
    return message_response(ctx, ctx.backend.get_message(record["channel_id"], record["message_id"]))


@route("PATCH", "/webhooks/{webhook_id}/{token}/messages/@original")
def edit_original_response(ctx: RequestContext) -> Any:
    record = _record(ctx)
    backend = ctx.backend
    if record["message_id"] is None and record["response_kind"] == "deferred":
        # Editing a deferred response materialises the response message.
        body = dict(ctx.body())
        if record["ephemeral"]:
            body["flags"] = int(body.get("flags") or 0) | EPHEMERAL_FLAG
        message = bot_message(ctx, record["channel_id"], interaction=record, body=body)
        record["message_id"] = message.id
        record["response_kind"] = "message"
        return message_response(ctx, message)
    if record["message_id"] is None:
        raise errors.unknown_message()
    message = backend.edit_message(record["channel_id"], record["message_id"], ctx.body())
    return message_response(ctx, message)


@route("DELETE", "/webhooks/{webhook_id}/{token}/messages/@original")
def delete_original_response(ctx: RequestContext) -> Any:
    record = _record(ctx)
    if record["message_id"] is not None:
        ctx.backend.delete_message(record["channel_id"], record["message_id"])
        record["message_id"] = None


@route("GET", "/webhooks/{webhook_id}/{token}/messages/{message_id}")
def get_followup(ctx: RequestContext) -> Any:
    record = _record(ctx)
    return message_response(ctx, ctx.backend.get_message(record["channel_id"], ctx.int_arg("message_id")))


@route("PATCH", "/webhooks/{webhook_id}/{token}/messages/{message_id}")
def edit_followup(ctx: RequestContext) -> Any:
    record = _record(ctx)
    message = ctx.backend.edit_message(record["channel_id"], ctx.int_arg("message_id"), ctx.body())
    return message_response(ctx, message)


@route("DELETE", "/webhooks/{webhook_id}/{token}/messages/{message_id}")
def delete_followup(ctx: RequestContext) -> Any:
    record = _record(ctx)
    ctx.backend.delete_message(record["channel_id"], ctx.int_arg("message_id"))
