"""Starlette RequestScopedMiddleware."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from anydi._container import Container


class RequestScopedMiddleware(BaseHTTPMiddleware):
    """Starlette middleware for managing request-scoped AnyDI context."""

    def __init__(self, app: ASGIApp, container: Container) -> None:
        super().__init__(app)
        self.container = container

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        async with self.container.arequest_context() as context:
            context.set(Request, request)
            return await call_next(request)
