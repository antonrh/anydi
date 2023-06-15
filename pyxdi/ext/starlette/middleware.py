from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

import pyxdi

_request_context: ContextVar[Request] = ContextVar("request_context")


class RequestScopedMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, di: pyxdi.PyxDI):
        super().__init__(app)
        self._di = di

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        token = _request_context.set(request)
        async with self._di.arequest_context():
            try:
                return await call_next(request)
            finally:
                _request_context.reset(token)


def get_request() -> Request:
    return _request_context.get()
