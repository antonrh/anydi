from __future__ import annotations

from types import TracebackType

from typing_extensions import Self


class HelloService:
    def __init__(self) -> None:
        self.started = False

    def say_hello(self, name: str) -> str:
        return f"Hello, {name}!"

    async def say_hello_async(self, name: str) -> str:
        return f"Hello, {name}!"

    def __enter__(self) -> Self:
        self.started = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.started = False
