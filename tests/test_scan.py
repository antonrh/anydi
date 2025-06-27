import pytest
from pytest_mock import MockerFixture

from anydi import Container

from tests.scan_app import ScanAppModule


class TestContainerScan:
    @pytest.fixture
    def container(self) -> Container:
        return Container()

    def test_scan_registers_all_dependencies(
        self, container: Container, mocker: MockerFixture
    ) -> None:
        inject_spy = mocker.spy(container, "inject")

        container.register_module(ScanAppModule)
        container.scan(["tests.scan_app"])

        # Expecting 7 total inject calls from all eligible @injectable functions
        assert inject_spy.call_count == 7

        from .scan_app.a.a3.handlers import a_a3_handler_1, a_a3_handler_2

        assert a_a3_handler_1() == "a.a1.str_provider"
        assert a_a3_handler_2().ident == "a.a1.str_provider"

    def test_scan_single_module_registers_limited_dependencies(
        self, container: Container, mocker: MockerFixture
    ) -> None:
        inject_spy = mocker.spy(container, "inject")

        container.register_module(ScanAppModule)
        container.scan("tests.scan_app.a.a3.handlers")

        # Expecting only 2 handlers to be registered from this specific module
        assert inject_spy.call_count == 2

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
