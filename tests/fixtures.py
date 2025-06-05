import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from typing import Annotated

from anydi import Module, provider
from anydi._container import Container


def func() -> str:
    return "func"


class Class:
    pass


def generator() -> Iterator[str]:
    yield "generator"


async def async_generator() -> AsyncIterator[str]:
    yield "async_generator"


async def coro() -> str:
    return "coro"


def event() -> Iterator[None]:
    yield


async def async_event() -> AsyncIterator[None]:
    yield


def iterator() -> Iterator:  # type: ignore[type-arg]
    yield


@dataclass(frozen=True)
class UniqueId:
    id: uuid.UUID = field(default_factory=uuid.uuid4)


class Service:
    def __init__(self, ident: str) -> None:
        self.ident = ident
        self.events: list[str] = []


class Resource:
    def __init__(self) -> None:
        self.called = False
        self.committed = False
        self.rolled_back = False

    def run(self) -> None:
        self.called = True

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class TestModule(Module):
    def configure(self, container: Container) -> None:
        container.register(
            Annotated[str, "msg1"], lambda: "Message 1", scope="singleton"
        )

    @provider(scope="singleton")
    def provide_msg2(self) -> Annotated[str, "msg2"]:
        return "Message 2"
