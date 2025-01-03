from typing import Annotated

from anydi import Container, Module, provider


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
