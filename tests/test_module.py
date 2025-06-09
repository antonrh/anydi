from typing import Annotated

import pytest

from anydi import Container, Module, provider

from tests.fixtures import TestModule


class TestContainerModuleRegistrator:
    @pytest.fixture
    def container(self) -> Container:
        return Container()

    def test_register_modules(self) -> None:
        container = Container(modules=[TestModule])

        assert container.is_registered(Annotated[str, "msg1"])
        assert container.is_registered(Annotated[str, "msg2"])

    def test_register_module_class(self, container: Container) -> None:
        container.register_module(TestModule)

        assert container.is_registered(Annotated[str, "msg1"])
        assert container.is_registered(Annotated[str, "msg2"])

    def test_register_module_instance(self, container: Container) -> None:
        container.register_module(TestModule())

        assert container.is_registered(Annotated[str, "msg1"])
        assert container.is_registered(Annotated[str, "msg2"])

    def test_register_module_path(self, container: Container) -> None:
        container.register_module("tests.test_module.TestModule")

        assert container.is_registered(Annotated[str, "msg1"])
        assert container.is_registered(Annotated[str, "msg2"])

    def test_register_module_function(self, container: Container) -> None:
        def configure(_container: Container) -> None:
            _container.register(str, lambda: "Message 1", scope="singleton")

        container.register_module(configure)

        assert container.is_registered(str)

    def test_register_module_ordered_providers(self, container: Container) -> None:
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

        container.register_module(OrderedModule)

        assert list(container.providers.keys()) == [
            Annotated[str, "dep3"],
            Annotated[str, "dep1"],
            Annotated[str, "dep2"],
        ]

    def test_register_module_invalid_path(self, container: Container) -> None:
        with pytest.raises(
            TypeError,
            match="The module must be a callable, a module type, or a module instance.",
        ):
            container.register_module("anydi.Container")
