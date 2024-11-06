import logging
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass

import pytest

from anydi import Container, auto, dep

from tests.fixtures import Service


@pytest.fixture
def container() -> Container:
    return Container()


def test_inject_auto_registered_log_message(
    container: Container, caplog: pytest.LogCaptureFixture
) -> None:
    class Service:
        pass

    with caplog.at_level(logging.DEBUG, logger="anydi"):

        @container.inject
        def handler(service: Service = dep()) -> None:
            pass

        assert caplog.messages == [
            "Cannot validate the `tests.test_injector"
            ".test_inject_auto_registered_log_message.<locals>.handler` parameter "
            "`service` with an annotation of `tests.test_injector"
            ".test_inject_auto_registered_log_message.<locals>.Service due to being "
            "in non-strict mode. It will be validated at the first call."
        ]


def test_inject_missing_annotation(container: Container) -> None:
    def handler(name=dep()) -> str:  # type: ignore[no-untyped-def]
        return name  # type: ignore[no-any-return]

    with pytest.raises(TypeError) as exc_info:
        container.inject(handler)

    assert str(exc_info.value) == (
        "Missing `tests.test_injector.test_inject_missing_annotation"
        ".<locals>.handler` parameter `name` annotation."
    )


def test_inject_unknown_dependency_using_strict_mode() -> None:
    container = Container(strict=True)

    def handler(message: str = dep()) -> None:
        pass

    with pytest.raises(LookupError) as exc_info:
        container.inject(handler)

    assert str(exc_info.value) == (
        "`tests.test_injector.test_inject_unknown_dependency_using_strict_mode"
        ".<locals>.handler` has an unknown dependency parameter `message` with an "
        "annotation of `str`."
    )


def test_inject(container: Container) -> None:
    @container.provider(scope="singleton")
    def ident_provider() -> str:
        return "1000"

    @container.provider(scope="singleton")
    def service_provider(ident: str) -> Service:
        return Service(ident=ident)

    @container.inject
    def func(name: str, service: Service = dep()) -> str:
        return f"{name} = {service.ident}"

    result = func(name="service ident")

    assert result == "service ident = 1000"


def test_inject_auto_marker(container: Container) -> None:
    @container.provider(scope="singleton")
    def message() -> str:
        return "test"

    @container.inject
    def func(message: str = auto) -> str:
        return message

    result = func()

    assert result == "test"


def test_inject_auto_marker_call(container: Container) -> None:
    @container.provider(scope="singleton")
    def message() -> str:
        return "test"

    @container.inject
    def func(message: str = auto()) -> str:
        return message

    result = func()

    assert result == "test"


def test_inject_class(container: Container) -> None:
    @container.provider(scope="singleton")
    def ident_provider() -> str:
        return "1000"

    @container.provider(scope="singleton")
    def service_provider(ident: str) -> Service:
        return Service(ident=ident)

    @container.inject
    class Handler:
        def __init__(self, name: str, service: Service = dep()) -> None:
            self.name = name
            self.service = service

        def handle(self) -> str:
            return f"{self.name} = {self.service.ident}"

    handler = Handler(name="service ident")

    result = handler.handle()

    assert result == "service ident = 1000"


def test_inject_dataclass(container: Container) -> None:
    @container.provider(scope="singleton")
    def ident_provider() -> str:
        return "1000"

    @container.provider(scope="singleton")
    def service_provider(ident: str) -> Service:
        return Service(ident=ident)

    @container.inject
    @dataclass
    class Handler:
        name: str
        service: Service = dep()

        def handle(self) -> str:
            return f"{self.name} = {self.service.ident}"

    handler = Handler(name="service ident")

    result = handler.handle()

    assert result == "service ident = 1000"


async def test_inject_with_sync_and_async_resources(container: Container) -> None:
    def ident_provider() -> Iterator[str]:
        yield "1000"

    async def service_provider(ident: str) -> AsyncIterator[Service]:
        yield Service(ident=ident)

    container.register(str, ident_provider, scope="singleton")
    container.register(Service, service_provider, scope="singleton")

    await container.astart()

    @container.inject
    async def func(name: str, service: Service = dep()) -> str:
        return f"{name} = {service.ident}"

    result = await func(name="service ident")

    assert result == "service ident = 1000"
