"""Fake transports: replacements for discord.py's HTTP client and webhook adapter.

``HTTPClient.request`` is the single chokepoint for nearly all REST calls;
interaction responses and followups go through the async webhook adapter
instead. Both are routed into the same backend route table, and backend errors
are raised as genuine ``discord.HTTPException`` subclasses with authentic
Discord error codes.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import discord
from discord.http import HTTPClient, Route

from . import routes
from .backend import Backend
from .errors import BackendError

_API_PREFIX = "/api/v"


class _FakeResponse:
    """Just enough of an aiohttp response for HTTPException construction."""

    def __init__(self, status: int) -> None:
        self.status = status
        self.reason = {400: "Bad Request", 403: "Forbidden", 404: "Not Found"}.get(status, "Error")
        self.headers: dict[str, str] = {}


def _raise_for(error: BackendError) -> None:
    response = _FakeResponse(error.status)
    data = error.to_json()
    if error.status == 403:
        raise discord.Forbidden(response, data)  # type: ignore[arg-type]
    if error.status == 404:
        raise discord.NotFound(response, data)  # type: ignore[arg-type]
    raise discord.HTTPException(response, data)  # type: ignore[arg-type]


def _path_of(url: str) -> str:
    # Strip "https://discord.com/api/v10" and query string from a routed URL.
    path = url.split("?", 1)[0]
    idx = path.find(_API_PREFIX)
    if idx != -1:
        path = path[idx + len(_API_PREFIX):]
        path = path[path.find("/"):]
    return path


class FakeHTTPClient(HTTPClient):
    """Drop-in ``HTTPClient`` whose requests hit the virtual backend."""

    def __init__(self, backend: Backend, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(loop)
        self.backend = backend
        # Interaction.__init__ reads the (name-mangled) session attribute.
        self._HTTPClient__session = None  # type: ignore[assignment]

    async def static_login(self, token: str) -> Any:
        self.token = token
        return dict(self.backend.bot_user)

    async def close(self) -> None:
        pass

    async def ws_connect(self, url: str, *, compress: int = 0) -> Any:
        raise RuntimeError("discord-py-test never opens a real gateway connection")

    async def get_from_cdn(self, url: str) -> bytes:
        try:
            return self.backend.cdn[url]
        except KeyError:
            _raise_for(BackendError(404, 0, "asset not found"))
            raise AssertionError  # unreachable

    async def request(
        self,
        route: Route,
        *,
        files: Optional[Any] = None,
        form: Optional[Any] = None,
        **kwargs: Any,
    ) -> Any:
        json = kwargs.get("json")
        file_list = list(files or [])
        if form is not None:
            payload, file_list = routes.parse_form(list(form), file_list)
            if payload is not None:
                json = payload
        try:
            return routes.dispatch(
                self.backend,
                route.method,
                _path_of(route.url),
                json=json,
                params=kwargs.get("params"),
                files=file_list,
            )
        except BackendError as exc:
            _raise_for(exc)


class FakeWebhookAdapter:
    """Replacement for ``discord.webhook.async_.AsyncWebhookAdapter``.

    Interaction responses, followups and webhook messages all funnel through
    the adapter's generic ``request``; everything else on the real adapter is
    a thin wrapper around it, so inheriting those wrappers is enough.
    """

    def __init__(self, backend: Backend) -> None:
        self.backend = backend

    def __getattr__(self, name: str) -> Any:
        # Delegate the named helpers (create_interaction_response, ...) to the
        # real adapter implementation, bound against this fake's request().
        from discord.webhook.async_ import AsyncWebhookAdapter

        real = getattr(AsyncWebhookAdapter, name)
        return real.__get__(self, FakeWebhookAdapter)

    async def request(
        self,
        route: Any,
        session: Any,
        *,
        payload: Optional[dict[str, Any]] = None,
        multipart: Optional[list[dict[str, Any]]] = None,
        files: Optional[Any] = None,
        params: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        json = payload
        file_list = list(files or [])
        if multipart:
            parsed, file_list = routes.parse_form(multipart, file_list)
            if parsed is not None:
                json = parsed
        try:
            return routes.dispatch(
                self.backend,
                route.method,
                _path_of(route.url),
                json=json,
                params=params,
                files=file_list,
            )
        except BackendError as exc:
            _raise_for(exc)
