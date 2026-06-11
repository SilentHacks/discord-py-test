"""Internal error types mapped onto real discord.py exceptions at the HTTP boundary."""

from __future__ import annotations

from typing import Any


class BackendError(Exception):
    """An error the virtual Discord backend wants to surface as a real HTTP error.

    These are translated into genuine ``discord.HTTPException`` subclasses
    (``Forbidden``, ``NotFound``, ...) carrying authentic Discord error codes,
    so bot code that branches on them behaves exactly as in production.
    """

    def __init__(self, status: int, code: int, message: str) -> None:
        super().__init__(f"{status} (error code: {code}): {message}")
        self.status = status
        self.code = code
        self.message = message

    def to_json(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message}


class RouteNotImplemented(BackendError):
    """Raised when the bot hits an API route the virtual backend does not implement yet.

    This is always loud: a testing tool must never silently pretend success.
    """

    def __init__(self, method: str, path: str) -> None:
        super().__init__(
            501,
            0,
            f"discord-py-test does not implement '{method} {path}' yet. "
            "Please open an issue if your bot needs this route.",
        )
        self.method = method
        self.path = path


class SetupError(Exception):
    """A test mis-set-up the virtual world (not a bot bug)."""


def missing_permissions() -> BackendError:
    return BackendError(403, 50013, "Missing Permissions")


def missing_access() -> BackendError:
    return BackendError(403, 50001, "Missing Access")


def unknown(entity: str, code: int) -> BackendError:
    return BackendError(404, code, f"Unknown {entity}")


def already_acknowledged() -> BackendError:
    return BackendError(400, 40060, "Interaction has already been acknowledged")
