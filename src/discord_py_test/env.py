"""Test environment lifecycle: attach a real bot to the virtual backend."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any, Optional

import discord
from discord.webhook.async_ import async_context

from .backend import Backend
from .errors import SetupError
from .gateway import FakeGateway
from .handles import GuildHandle, UserHandle
from .http import FakeHTTPClient, FakeWebhookAdapter

# Coroutines that are long-lived background machinery, not work to settle on.
_BACKGROUND_COROS = ("__timeout_task_impl",)


class Env:
    """A running test environment around a single bot.

    Use via :func:`discord_py_test.run`::

        async with dpt.run(bot) as env:
            guild = env.create_guild()
            ...
    """

    def __init__(self, bot: discord.Client, *, strict_sync: bool = True) -> None:
        self.bot = bot
        self.strict_sync = strict_sync
        self.backend = Backend()
        self.errors: list[BaseException] = []
        self._guilds: list[GuildHandle] = []
        self._tasks: list[asyncio.Task[Any]] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._orig_create_task: Any = None
        self._adapter_token: Any = None
        self._started = False

    # ------------------------------------------------------------- lifecycle

    async def start(self) -> None:
        if self._started:
            raise SetupError("Env already started")
        self._started = True
        loop = asyncio.get_running_loop()
        self._loop = loop

        # Track every task spawned while the env is live so settle() can wait
        # for the bot to finish reacting without guessing with sleeps.
        self._orig_create_task = loop.create_task

        def tracking_create_task(coro: Any, **kwargs: Any) -> asyncio.Task[Any]:
            task = self._orig_create_task(coro, **kwargs)
            self._tasks.append(task)
            return task

        loop.create_task = tracking_create_task  # type: ignore[method-assign]

        state = self.bot._connection
        fake_http = FakeHTTPClient(self.backend, loop)
        self.bot.http = fake_http  # type: ignore[misc]
        state.http = fake_http
        tree = getattr(self.bot, "tree", None)
        if tree is not None:
            # CommandTree captures its own HTTP reference at construction time.
            tree._http = fake_http
        # No guilds arrive before READY; don't wait for stragglers.
        state.guild_ready_timeout = 0.0
        self._adapter_token = async_context.set(FakeWebhookAdapter(self.backend))  # type: ignore[arg-type]

        gateway = FakeGateway(state)
        self.backend.subscribers.append(gateway.feed)

        self._capture_errors()
        await self.bot.login("dpt.fake.token")
        gateway.feed(
            "READY",
            {
                "v": 10,
                "user": self.backend.bot_user,
                "guilds": [],
                "session_id": "dpt-session",
                "resume_gateway_url": "wss://dpt.invalid",
                "shard": [0, 1],
                "application": {"id": str(self.backend.application_id), "flags": 0},
            },
        )
        await self.settle()

    async def shutdown(self) -> None:
        if self._adapter_token is not None:
            async_context.reset(self._adapter_token)
        if self._loop is not None and self._orig_create_task is not None:
            self._loop.create_task = self._orig_create_task  # type: ignore[method-assign]
        current = asyncio.current_task()
        to_cancel = [t for t in self._tasks if t is not current and not t.done()]
        for task in to_cancel:
            task.cancel()
        await asyncio.gather(*to_cancel, return_exceptions=True)

    async def settle(self, timeout: float = 5.0, idle: float = 0.05) -> None:
        """Wait until the bot has finished reacting to injected events.

        Waits for all tracked tasks to complete. Tasks that make no progress
        within ``idle`` seconds (e.g. a handler blocked in ``wait_for`` for a
        future user action) are left running; tasks still pending after
        ``timeout`` raise.
        """
        assert self._loop is not None
        deadline = self._loop.time() + timeout
        # Give freshly-scheduled callbacks a chance to run first.
        for _ in range(3):
            await asyncio.sleep(0)
        while True:
            self._tasks = [t for t in self._tasks if not t.done()]
            pending = [
                t
                for t in self._tasks
                if getattr(t.get_coro(), "__qualname__", "").split(".")[-1] not in _BACKGROUND_COROS
            ]
            if not pending:
                return
            done, _ = await asyncio.wait(pending, timeout=idle, return_when=asyncio.FIRST_COMPLETED)
            if not done:
                if self._loop.time() > deadline:
                    raise TimeoutError(f"bot did not settle; pending tasks: {pending}")
                return  # remaining tasks are blocked waiting on future input

    # -------------------------------------------------------- error capture

    def _capture_errors(self) -> None:
        async def on_command_error(_ctx: Any, error: BaseException) -> None:
            self.errors.append(error)

        add_listener = getattr(self.bot, "add_listener", None)
        if add_listener is not None:
            add_listener(on_command_error, "on_command_error")

        tree = getattr(self.bot, "tree", None)
        if tree is not None:
            original = tree.on_error

            async def on_tree_error(interaction: Any, error: BaseException) -> None:
                self.errors.append(error)
                await original(interaction, error)

            tree.on_error = on_tree_error

    # -------------------------------------------------------------- builders

    def create_user(self, name: str) -> UserHandle:
        return UserHandle(self, self.backend.make_user(name))

    def create_guild(self, name: str = "Test Guild") -> GuildHandle:
        handle = GuildHandle(self, self.backend.create_guild(name))
        self._guilds.append(handle)
        return handle

    @property
    def guild(self) -> GuildHandle:
        """The first created guild, for the common single-guild case."""
        if not self._guilds:
            raise SetupError("No guild created yet; call env.create_guild() first")
        return self._guilds[0]


class run:
    """``async with dpt.run(bot) as env:`` — attach, fake-login, READY."""

    def __init__(self, bot: discord.Client, **options: Any) -> None:
        self._env = Env(bot, **options)

    async def __aenter__(self) -> Env:
        await self._env.start()
        return self._env

    async def __aexit__(self, *exc_info: Any) -> None:
        await self._env.shutdown()
