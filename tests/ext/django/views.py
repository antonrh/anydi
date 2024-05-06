from typing import Annotated

from django.http import HttpRequest, HttpResponse

import anydi


def get_setting(
    request: HttpRequest,
    message: Annotated[str, "django.conf.settings.HELLO_MESSAGE"] = anydi.auto,
) -> HttpResponse:
    return HttpResponse(message)


async def get_setting_async(
    request: HttpRequest,
    message: Annotated[str, "django.conf.settings.HELLO_MESSAGE"] = anydi.auto,
) -> HttpResponse:
    return HttpResponse(message)


def get_configured_dependency(
    request: HttpRequest,
    message: Annotated[str, "configured-string"] = anydi.auto,
) -> HttpResponse:
    return HttpResponse(message)
