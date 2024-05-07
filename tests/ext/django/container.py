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
    def hello_service() -> Iterator[HelloService]:
        with HelloService() as hello_service:
            yield hello_service

    # @container.provider(scope="request")
    # def request_id() -> Annotated[str, "request-id"]:
    #     return uuid.uuid4().hex

    container.register(
        Annotated[str, "request-id"],
        lambda: uuid.uuid4().hex,
        scope="request",
    )
