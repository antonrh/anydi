from typing import Any, Callable

from asgiref.sync import iscoroutinefunction
from django.http import HttpRequest
from django.utils.decorators import sync_and_async_middleware

from ._container import container


@sync_and_async_middleware
def request_scoped_middleware(
    get_response: Callable[..., Any],
) -> Callable[..., Any]:
    if iscoroutinefunction(get_response):

        async def async_middleware(request: HttpRequest) -> Any:
            async with container.arequest_context() as context:
                context.set(HttpRequest, request)
                return await get_response(request)

        return async_middleware

    def middleware(request: HttpRequest) -> Any:
        with container.request_context() as context:
            context.set(HttpRequest, request)
            return get_response(request)

    return middleware
