from typing import Any

from django.http import HttpRequest
from ninja import Router

import anydi

from tests.ext.django.services import HelloService

router = Router()


@router.get("/say-hello")
def say_hello(
    request: HttpRequest,
    name: str,
    hello_service: HelloService = anydi.auto,
) -> Any:
    assert hello_service.started
    return hello_service.say_hello(name)


@router.get("/say-hello-async")
async def say_hello_async(
    request: HttpRequest,
    name: str,
    hello_service: HelloService = anydi.auto,
) -> Any:
    assert hello_service.started
    return await hello_service.say_hello_async(name)
