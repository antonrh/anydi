"""Starlette RequestScopedMiddleware."""
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from pyxdi import PyxDI


class RequestScopedMiddleware(BaseHTTPMiddleware):
    """Starlette middleware for managing request-scoped PyxDI context."""

    def __init__(self, app: ASGIApp, di: PyxDI) -> None:
        """Initialize the RequestScopedMiddleware.

        Args:
            app: The ASGI application.
            di: The PyxDI container.
        """
        super().__init__(app)
        self._di = di

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
        async with self._di.arequest_context():
            return await call_next(request)
