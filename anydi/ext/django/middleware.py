from typing import Callable

from asgiref.sync import iscoroutinefunction
from django.http import HttpRequest, HttpResponse
from django.utils.decorators import sync_and_async_middleware

from ._container import container


@sync_and_async_middleware  # type: ignore[misc]
def request_scoped_middleware(
    get_response: Callable[[HttpRequest], HttpResponse],
) -> Callable[[HttpRequest], HttpResponse]:
    if iscoroutinefunction(get_response):

        async def async_middleware(request: HttpRequest) -> HttpResponse:
            async with container.arequest_context():
                return await get_response(request)

        return async_middleware

    def middleware(request: HttpRequest) -> HttpResponse:
        with container.request_context():
            return get_response(request)

    return middleware
