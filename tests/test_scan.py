import pytest

from anydi import Container

from tests.scan_app import ScanAppModule


class TestContainerScan:
    @pytest.fixture
    def container(self) -> Container:
        return Container()

    def test_scan(self, container: Container) -> None:
        container.register_module(ScanAppModule)
        container.scan(["tests.scan_app"])

        from .scan_app.a.a3.handlers import a_a3_handler_1, a_a3_handler_2

        assert a_a3_handler_1() == "a.a1.str_provider"
        assert a_a3_handler_2().ident == "a.a1.str_provider"

    def test_scan_single_package(self, container: Container) -> None:
        container.register_module(ScanAppModule)
        container.scan("tests.scan_app.a.a3.handlers")

        from .scan_app.a.a3.handlers import a_a3_handler_1

        assert a_a3_handler_1() == "a.a1.str_provider"

    def test_scan_non_existing_tag(self, container: Container) -> None:
        container.scan(["tests.scan_app"], tags=["non_existing_tag"])

        assert not container.providers

    def test_scan_tagged(self, container: Container) -> None:
        container.register_module(ScanAppModule)
        container.scan(["tests.scan_app.a"], tags=["inject"])

        from .scan_app.a.a3.handlers import a_a3_handler_1

        assert a_a3_handler_1() == "a.a1.str_provider"
