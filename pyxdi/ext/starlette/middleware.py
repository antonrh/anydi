from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

import pyxdi


class RequestScopedMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, di: pyxdi.PyxDI):
        super().__init__(app)
        self._di = di

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        async with await self._di.arequest_context() as ctx:
            ctx.set(Request, instance=request)
            return await call_next(request)
