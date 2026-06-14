---
title: "Parity matrix"
description: "What SimCord's virtual Discord implements today — messages, slash commands, components, permissions, threads and more — plus the exact list of supported REST routes. Anything unimplemented fails loudly."
---

# Parity matrix

What the virtual Discord implements today. Anything not listed fails **loudly** with a
`RouteNotImplemented` error naming the route — please open a
[parity gap issue](https://github.com/SilentHacks/simcord/issues/new?template=parity-gap.md)
if your bot needs it.

| Area | Status | Notes |
| --- | --- | --- |
| Login / READY / setup_hook | ✅ | Real discord.py login flow, application info |
| Gateway intents | ✅ | Server-side gating, `message_content` censoring, member chunking, 4014 — see the [Intents guide](guides/intents.md) |
| Messages (send/edit/delete/fetch/history) | ✅ | Content & embed limits enforced (`50035`) |
| Bulk delete (`purge` / `delete_messages`) | ✅ | 2–100 messages, single `MESSAGE_DELETE_BULK`, audit-logged |
| Embeds, attachments, replies, mentions | ✅ | In-memory CDN; `attachment.read()` works |
| Pins | ✅ | Current paginated endpoints |
| Typing | ✅ | Both directions |
| Reactions | ✅ | Add/remove/list, clear-all & clear-emoji, gateway events |
| DM channels | ✅ | User→bot and bot→user |
| Threads | ✅ | Create (standalone & from message), messaging within |
| Forum posts | ✅ | `ForumChannel.create_thread` (starter message + `applied_tags`); tag config via edit |
| Prefix commands (`ext.commands`) | ✅ | Converters, checks, cooldowns, error handlers |
| Permissions engine | ✅ | Overwrites, hierarchy, timeouts, owner/admin |
| Slash commands | ✅ | Options, choices, resolved data, subcommand groups |
| App command permissions | ✅ | `AppCommand.fetch_permissions`; seed via `guild.set_command_permissions` |
| Context menus (user & message) | ✅ | |
| Autocomplete | ✅ | |
| Interaction lifecycle | ✅ | Defer, followups, `@original` ops, `40060` on double-ack |
| Ephemeral semantics | ✅ | Visibility-aware history and component access |
| Buttons / selects / modals | ✅ | Real `View` dispatch; disabled/missing rejected |
| User/role/channel/mentionable selects | ✅ | Pass the handles a user could pick; resolved data built |
| Bot restart / persistent views | ✅ | `env.restart_bot()` replays the world; persistent views re-attach |
| Members (join/leave, kick/ban/unban, nick, roles, timeout) | ✅ | Hierarchy enforced; `fetch_members` listing |
| Roles (create/edit/delete) | ✅ | |
| Guilds (create/edit) | ✅ | `Client.create_guild`, `Guild.edit`; `GUILD_UPDATE` audit |
| Channels (create/edit/delete, overwrites) | ✅ | Runtime create + list; text, voice, stage, category & forum kinds |
| Webhooks | ✅ | Create, execute, fetch/edit/delete (by id or token), guild listing |
| Fault injection / HTTP log | ✅ | `env.inject_error`, `env.http_log` |
| Audit logs | ✅ | Recorded for ban/kick/role/member/channel/event actions; `guild.audit_logs()`, filtering |
| Polls | ✅ | Message-level poll object; `actor.vote`, expiry (route + `advance_time`), vote events |
| Scheduled events | ✅ | CRUD + subscribe/unsubscribe; auto status transitions via `advance_time` |
| Voice state | ✅ | State only — never audio; join/leave/move/mute, request-to-speak, `VOICE_STATE_UPDATE` |
| Stage instances | ✅ | `StageChannel.create_instance`/`fetch_instance`, `StageInstance.edit`/`delete`, gateway events |
| Invites | ✅ | Create/list/fetch/delete, gateway events |
| Emojis & stickers | ✅ | Guild expression CRUD, update events; application-owned emojis (`Client.create_application_emoji`, `fetch_application_emojis`) |
| Auto-moderation | ✅ | Rule CRUD + keyword & mention-spam execution (block/alert) on send |
| View timeout fast-forward (`advance_time`) | ✅ | Virtual clock; fires view timeouts, cooldowns, sleep chains |
| Rate limit simulation | ❌ | Deliberate: tests stay fast; use `inject_error` for 429 paths |
| Multiple bots in one Env | ❌ | The backend broadcasts to N clients, but `Env` currently drives one bot |
| Sharding simulation | ❌ | Single virtual shard |

## Implemented routes

This section is generated from the route table (`python -m simcord.parity`),
so it is exact by construction.

<!-- routes:begin (generated — do not edit by hand) -->

108 routes implemented. Anything else fails loudly with `RouteNotImplemented`.

| Method | Route |
| --- | --- |
| `GET` | `/applications/{application_id}/commands` |
| `PUT` | `/applications/{application_id}/commands` |
| `GET` | `/applications/{application_id}/emojis` |
| `POST` | `/applications/{application_id}/emojis` |
| `GET` | `/applications/{application_id}/emojis/{emoji_id}` |
| `PATCH` | `/applications/{application_id}/emojis/{emoji_id}` |
| `DELETE` | `/applications/{application_id}/emojis/{emoji_id}` |
| `GET` | `/applications/{application_id}/guilds/{guild_id}/commands` |
| `PUT` | `/applications/{application_id}/guilds/{guild_id}/commands` |
| `GET` | `/applications/{application_id}/guilds/{guild_id}/commands/{command_id}/permissions` |
| `GET` | `/channels/{channel_id}` |
| `PATCH` | `/channels/{channel_id}` |
| `DELETE` | `/channels/{channel_id}` |
| `GET` | `/channels/{channel_id}/invites` |
| `POST` | `/channels/{channel_id}/invites` |
| `GET` | `/channels/{channel_id}/messages` |
| `POST` | `/channels/{channel_id}/messages` |
| `POST` | `/channels/{channel_id}/messages/bulk-delete` |
| `GET` | `/channels/{channel_id}/messages/pins` |
| `PUT` | `/channels/{channel_id}/messages/pins/{message_id}` |
| `DELETE` | `/channels/{channel_id}/messages/pins/{message_id}` |
| `GET` | `/channels/{channel_id}/messages/{message_id}` |
| `PATCH` | `/channels/{channel_id}/messages/{message_id}` |
| `DELETE` | `/channels/{channel_id}/messages/{message_id}` |
| `DELETE` | `/channels/{channel_id}/messages/{message_id}/reactions` |
| `GET` | `/channels/{channel_id}/messages/{message_id}/reactions/{emoji}` |
| `DELETE` | `/channels/{channel_id}/messages/{message_id}/reactions/{emoji}` |
| `PUT` | `/channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me` |
| `DELETE` | `/channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me` |
| `DELETE` | `/channels/{channel_id}/messages/{message_id}/reactions/{emoji}/{user_id}` |
| `POST` | `/channels/{channel_id}/messages/{message_id}/threads` |
| `PUT` | `/channels/{channel_id}/permissions/{target_id}` |
| `DELETE` | `/channels/{channel_id}/permissions/{target_id}` |
| `GET` | `/channels/{channel_id}/polls/{message_id}/answers/{answer_id}` |
| `POST` | `/channels/{channel_id}/polls/{message_id}/expire` |
| `POST` | `/channels/{channel_id}/threads` |
| `POST` | `/channels/{channel_id}/typing` |
| `GET` | `/channels/{channel_id}/webhooks` |
| `POST` | `/channels/{channel_id}/webhooks` |
| `POST` | `/guilds` |
| `GET` | `/guilds/{guild_id}` |
| `PATCH` | `/guilds/{guild_id}` |
| `GET` | `/guilds/{guild_id}/audit-logs` |
| `GET` | `/guilds/{guild_id}/auto-moderation/rules` |
| `POST` | `/guilds/{guild_id}/auto-moderation/rules` |
| `GET` | `/guilds/{guild_id}/auto-moderation/rules/{rule_id}` |
| `PATCH` | `/guilds/{guild_id}/auto-moderation/rules/{rule_id}` |
| `DELETE` | `/guilds/{guild_id}/auto-moderation/rules/{rule_id}` |
| `GET` | `/guilds/{guild_id}/bans` |
| `GET` | `/guilds/{guild_id}/bans/{user_id}` |
| `PUT` | `/guilds/{guild_id}/bans/{user_id}` |
| `DELETE` | `/guilds/{guild_id}/bans/{user_id}` |
| `GET` | `/guilds/{guild_id}/channels` |
| `POST` | `/guilds/{guild_id}/channels` |
| `GET` | `/guilds/{guild_id}/emojis` |
| `POST` | `/guilds/{guild_id}/emojis` |
| `GET` | `/guilds/{guild_id}/emojis/{emoji_id}` |
| `PATCH` | `/guilds/{guild_id}/emojis/{emoji_id}` |
| `DELETE` | `/guilds/{guild_id}/emojis/{emoji_id}` |
| `GET` | `/guilds/{guild_id}/invites` |
| `GET` | `/guilds/{guild_id}/members` |
| `GET` | `/guilds/{guild_id}/members/{user_id}` |
| `PATCH` | `/guilds/{guild_id}/members/{user_id}` |
| `DELETE` | `/guilds/{guild_id}/members/{user_id}` |
| `PUT` | `/guilds/{guild_id}/members/{user_id}/roles/{role_id}` |
| `DELETE` | `/guilds/{guild_id}/members/{user_id}/roles/{role_id}` |
| `GET` | `/guilds/{guild_id}/roles` |
| `POST` | `/guilds/{guild_id}/roles` |
| `PATCH` | `/guilds/{guild_id}/roles/{role_id}` |
| `DELETE` | `/guilds/{guild_id}/roles/{role_id}` |
| `GET` | `/guilds/{guild_id}/scheduled-events` |
| `POST` | `/guilds/{guild_id}/scheduled-events` |
| `GET` | `/guilds/{guild_id}/scheduled-events/{event_id}` |
| `PATCH` | `/guilds/{guild_id}/scheduled-events/{event_id}` |
| `DELETE` | `/guilds/{guild_id}/scheduled-events/{event_id}` |
| `GET` | `/guilds/{guild_id}/scheduled-events/{event_id}/users` |
| `GET` | `/guilds/{guild_id}/stickers` |
| `POST` | `/guilds/{guild_id}/stickers` |
| `GET` | `/guilds/{guild_id}/stickers/{sticker_id}` |
| `PATCH` | `/guilds/{guild_id}/stickers/{sticker_id}` |
| `DELETE` | `/guilds/{guild_id}/stickers/{sticker_id}` |
| `PATCH` | `/guilds/{guild_id}/voice-states/@me` |
| `PATCH` | `/guilds/{guild_id}/voice-states/{user_id}` |
| `GET` | `/guilds/{guild_id}/webhooks` |
| `POST` | `/interactions/{interaction_id}/{token}/callback` |
| `GET` | `/invites/{code}` |
| `DELETE` | `/invites/{code}` |
| `GET` | `/oauth2/applications/@me` |
| `POST` | `/stage-instances` |
| `GET` | `/stage-instances/{channel_id}` |
| `PATCH` | `/stage-instances/{channel_id}` |
| `DELETE` | `/stage-instances/{channel_id}` |
| `GET` | `/users/@me` |
| `POST` | `/users/@me/channels` |
| `GET` | `/users/{user_id}` |
| `GET` | `/webhooks/{webhook_id}` |
| `PATCH` | `/webhooks/{webhook_id}` |
| `DELETE` | `/webhooks/{webhook_id}` |
| `GET` | `/webhooks/{webhook_id}/{token}` |
| `POST` | `/webhooks/{webhook_id}/{token}` |
| `PATCH` | `/webhooks/{webhook_id}/{token}` |
| `DELETE` | `/webhooks/{webhook_id}/{token}` |
| `GET` | `/webhooks/{webhook_id}/{token}/messages/@original` |
| `PATCH` | `/webhooks/{webhook_id}/{token}/messages/@original` |
| `DELETE` | `/webhooks/{webhook_id}/{token}/messages/@original` |
| `GET` | `/webhooks/{webhook_id}/{token}/messages/{message_id}` |
| `PATCH` | `/webhooks/{webhook_id}/{token}/messages/{message_id}` |
| `DELETE` | `/webhooks/{webhook_id}/{token}/messages/{message_id}` |

<!-- routes:end -->
