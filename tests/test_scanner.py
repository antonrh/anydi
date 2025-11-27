import pytest
from pytest_mock import MockerFixture

from anydi import Container

from tests.scan_app import ScanAppModule


class TestContainerScanner:
    @pytest.fixture
    def container(self) -> Container:
        return Container()

    def test_scan_registers_all_dependencies(
        self, container: Container, mocker: MockerFixture
    ) -> None:
        inject_spy = mocker.spy(container, "inject")

        container.register_module(ScanAppModule)
        container.scan(["tests.scan_app"])

        # Expecting 4 total inject calls from all eligible @injectable functions
        assert inject_spy.call_count == 4

        from .scan_app.a.a3.handlers import a_a3_handler_1

        assert a_a3_handler_1() == "a.a1.str_provider"

    def test_scan_single_module_registers_limited_dependencies(
        self, container: Container, mocker: MockerFixture
    ) -> None:
        inject_spy = mocker.spy(container, "inject")

        container.register_module(ScanAppModule)
        container.scan("tests.scan_app.a.a3.handlers")

        # Expecting only 1 handler to be registered from this specific module
        assert inject_spy.call_count == 1

        from .scan_app.a.a3.handlers import a_a3_handler_1

        assert a_a3_handler_1() == "a.a1.str_provider"

    def test_scan_with_unknown_tag_registers_nothing(
        self, container: Container, mocker: MockerFixture
    ) -> None:
        inject_spy = mocker.spy(container, "inject")

        container.scan(["tests.scan_app"], tags=["non_existing_tag"])

        # No injectable functions should be picked up with unmatched tags
        inject_spy.assert_not_called()

    def test_scan_with_matching_tag_registers_only_matching_dependencies(
        self, container: Container, mocker: MockerFixture
    ) -> None:
        inject_spy = mocker.spy(container, "inject")

        container.register_module(ScanAppModule)
        container.scan(["tests.scan_app"], tags=["inject"])

        # Only handlers with @injectable(..., tags=["inject"]) should be included
        assert inject_spy.call_count == 1

        from .scan_app.a.a3.handlers import a_a3_handler_1

        assert a_a3_handler_1() == "a.a1.str_provider"

    def test_scan_registers_provided_classes(
        self, container: Container, mocker: MockerFixture
    ) -> None:
        register_spy = mocker.spy(container, "register")

        container.scan(["tests.scan_app.c"])

        # Should register 2 @provided classes (SingletonService and TransientService)
        assert register_spy.call_count == 2

        from .scan_app.c.services import SingletonService, TransientService

        # Verify classes are registered
        assert container.is_registered(SingletonService)
        assert container.is_registered(TransientService)

        # Verify they can be resolved
        singleton_service = container.resolve(SingletonService)
        assert singleton_service.name == "singleton_service"

        transient_service = container.resolve(TransientService)
        assert transient_service.name == "transient_service"
        assert transient_service.singleton_service is singleton_service

    def test_scan_skips_already_registered_provided_classes(
        self, container: Container, mocker: MockerFixture
    ) -> None:
        from .scan_app.c.services import SingletonService

        # Manually register the class first
        container.register(SingletonService)

        register_spy = mocker.spy(container, "register")

        container.scan(["tests.scan_app.c"])

        # Should only register TransientService (SingletonService already registered)
        assert register_spy.call_count == 1

        # Verify both classes are registered
        assert container.is_registered(SingletonService)
