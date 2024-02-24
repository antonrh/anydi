import pytest
from typing_extensions import Annotated

from pyxdi import Container, Module, provider
from pyxdi._module import ProviderDecoratorArgs  # noqa


@pytest.fixture
def container() -> Container:
    return Container()


class TestModule(Module):
    def configure(self, container: Container) -> None:
        container.register_provider(
            Annotated[str, "msg1"], lambda: "Message 1", scope="singleton"
        )

    @provider(scope="singleton")
    def provide_msg2(self) -> Annotated[str, "msg2"]:
        return "Message 2"


def test_register_modules() -> None:
    container = Container(modules=[TestModule])

    assert container.has_provider(Annotated[str, "msg1"])
    assert container.has_provider(Annotated[str, "msg2"])


def test_register_module_class(container: Container) -> None:
    container.register_module(TestModule)

    assert container.has_provider(Annotated[str, "msg1"])
    assert container.has_provider(Annotated[str, "msg2"])


def test_register_module_instance(container: Container) -> None:
    container.register_module(TestModule())

    assert container.has_provider(Annotated[str, "msg1"])
    assert container.has_provider(Annotated[str, "msg2"])


def test_register_module_function(container: Container) -> None:
    def configure(container: Container) -> None:
        container.register_provider(str, lambda: "Message 1", scope="singleton")

    container.register_module(configure)

    assert container.has_provider(str)


class OrderedModule(Module):
    @provider(scope="singleton")
    def dep3(self) -> Annotated[str, "dep3"]:
        return "dep3"

    @provider(scope="singleton")
    def dep1(self) -> Annotated[str, "dep1"]:
        return "dep1"

    @provider(scope="singleton")
    def dep2(self) -> Annotated[str, "dep2"]:
        return "dep2"


def test_register_module_ordered_providers(container: Container) -> None:
    container.register_module(OrderedModule)

    assert list(container.providers.keys()) == [
        Annotated[str, "dep3"],
        Annotated[str, "dep1"],
        Annotated[str, "dep2"],
    ]


def test_module_provider_decorator() -> None:
    class TestModule(Module):
        @provider(scope="singleton", override=True)
        def provider(self) -> str:
            return "test"

    assert getattr(TestModule.provider, "__provider__") == ProviderDecoratorArgs(
        scope="singleton",
        override=True,
    )
