from __future__ import annotations

from typing import Annotated, Iterator

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
