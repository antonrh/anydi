"""Starlette middleware for AnyDI scoped contexts."""

from __future__ import annotations

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
        # Only handle HTTP requests
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Create request-scoped context for the HTTP request
        async with self.container.arequest_context() as context:
            # Create Request instance and inject it into context
            request = Request(scope, receive=receive, send=send)
            context.set(Request, request)

            # Process the HTTP request
            await self.app(scope, receive, send)


class WebSocketScopedMiddleware:
    """ASGI middleware for managing websocket-scoped AnyDI context."""

    def __init__(self, app: ASGIApp, container: Container) -> None:
        self.app = app
        self.container = container

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Only handle WebSocket connections
        if scope["type"] != "websocket":
            await self.app(scope, receive, send)
            return

        # Create WebSocket-scoped context for the entire connection
        async with self.container.ascoped_context("websocket") as context:
            # Create WebSocket instance and inject it into context
            websocket = WebSocket(scope, receive=receive, send=send)
            context.set(WebSocket, websocket)

            # Process the WebSocket connection
            await self.app(scope, receive, send)
