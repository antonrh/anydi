"""Starlette RequestScopedMiddleware."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from anydi import Container


class RequestScopedMiddleware(BaseHTTPMiddleware):
    """Starlette middleware for managing request-scoped AnyDI context."""

    def __init__(self, app: ASGIApp, container: Container) -> None:
        """Initialize the RequestScopedMiddleware.

        Args:
            app: The ASGI application.
            container: The container.
        """
        super().__init__(app)
        self.container = container

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Dispatch the request and handle the response.

        Args:
            request: The incoming request.
            call_next: The next request-response endpoint.

        Returns:
            The response to the request.
        """
        async with self.container.arequest_context():
            return await call_next(request)
