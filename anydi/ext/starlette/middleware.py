"""Starlette middleware for AnyDI scoped contexts."""

from __future__ import annotations

try:
    import starlette  # noqa: F401
except ImportError:  # pragma: no cover - CI installs it
    message = (
        "This extension needs `starlette`. Install it with `pip install starlette`."
    )
    raise ImportError(message) from None

from contextlib import AsyncExitStack

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocket

from anydi import Container


class RequestScopedMiddleware:
    """ASGI middleware for managing request-scoped AnyDI context."""

    def __init__(self, app: ASGIApp, container: Container) -> None:
        self.app = app
        self.container = container

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Only handle HTTP requests or WebSocket connections
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        # A mounted application replaces `scope["app"]` with itself.
        scope["anydi.container"] = self.container

        async with AsyncExitStack() as stack:
            # Create request context first (parent scope)
            request_context = await stack.enter_async_context(
                self.container.arequest_context()
            )

            # For WebSocket connections, create websocket context (child scope)
            websocket_context = None
            if scope["type"] == "websocket" and self.container.has_scope("websocket"):
                websocket_context = await stack.enter_async_context(
                    self.container.ascoped_context("websocket")
                )

            if scope["type"] == "http":
                request = Request(scope, receive=receive, send=send)
                request_context.set(Request, request)
            else:
                websocket = WebSocket(scope, receive=receive, send=send)
                request_context.set(WebSocket, websocket)
                if websocket_context is not None:
                    websocket_context.set(WebSocket, websocket)

            await self.app(scope, receive, send)
