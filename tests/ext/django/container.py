from __future__ import annotations

import uuid
from typing import Iterator

from typing_extensions import Annotated

import anydi

from .services import HelloService


def configure(container: anydi.Container) -> None:
    container.register(
        Annotated[str, "configured-string"],
        lambda: "This is configured string",
        scope="singleton",
    )

    @container.provider(scope="singleton")
    def hello_service() -> HelloService:
        return HelloService()

    @container.provider(scope="singleton")
    def start_hello_service(hello_service: HelloService) -> Iterator[None]:
        with hello_service:
            yield

    # @container.provider(scope="request")
    # def request_id() -> Annotated[str, "request-id"]:
    #     return uuid.uuid4().hex

    container.register(
        Annotated[str, "request-id"],
        lambda: uuid.uuid4().hex,
        scope="request",
    )
