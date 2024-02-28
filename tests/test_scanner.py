import pytest

from anydi import Container, injectable
from anydi._scanner import InjectDecoratorArgs  # noqa

from .scan_app import ScanAppModule


@pytest.fixture
def container() -> Container:
    return Container()


def test_scan(container: Container) -> None:
    container.register_module(ScanAppModule)
    container.scan(["tests.scan_app"])

    from .scan_app.a.a3.handlers import a_a3_handler_1, a_a3_handler_2

    assert a_a3_handler_1() == "a.a1.str_provider"
    assert a_a3_handler_2().ident == "a.a1.str_provider"


def test_scan_single_package(container: Container) -> None:
    container.register_module(ScanAppModule)
    container.scan("tests.scan_app.a.a3.handlers")

    from .scan_app.a.a3.handlers import a_a3_handler_1

    assert a_a3_handler_1() == "a.a1.str_provider"


def test_scan_non_existing_tag(container: Container) -> None:
    container.scan(["tests.scan_app"], tags=["non_existing_tag"])

    assert not container.providers


def test_scan_tagged(container: Container) -> None:
    container.register_module(ScanAppModule)
    container.scan(["tests.scan_app.a"], tags=["inject"])

    from .scan_app.a.a3.handlers import a_a3_handler_1

    assert a_a3_handler_1() == "a.a1.str_provider"


def test_inject_decorator_no_args() -> None:
    @injectable
    def my_func() -> None:
        pass

    assert getattr(my_func, "__injectable__") == InjectDecoratorArgs(
        wrapped=True,
        tags=None,
    )


def test_inject_decorator_no_args_provided() -> None:
    @injectable()
    def my_func() -> None:
        pass

    assert getattr(my_func, "__injectable__") == InjectDecoratorArgs(
        wrapped=True,
        tags=None,
    )


def test_inject_decorator() -> None:
    @injectable(tags=["tag1", "tag2"])
    def my_func() -> None:
        pass

    assert getattr(my_func, "__injectable__") == InjectDecoratorArgs(
        wrapped=True,
        tags=["tag1", "tag2"],
    )
