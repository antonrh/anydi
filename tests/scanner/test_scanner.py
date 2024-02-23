import pytest

from pyxdi import PyxDI, injectable

from tests.scanner.app import AppModule


@pytest.fixture(scope="function")
def di() -> PyxDI:
    return PyxDI()


def test_scan_packages(di: PyxDI) -> None:
    di.register_module(AppModule)
    di.scan(["tests.scanner.app"])

    from .app.a.a3.handlers import a_a3_handler_1, a_a3_handler_2

    assert a_a3_handler_1() == "a.a1.str_provider"
    assert a_a3_handler_2().ident == "a.a1.str_provider"


def test_scan_single_module(di: PyxDI) -> None:
    di.register_module(AppModule)
    di.scan("tests.scanner.app.a.a3.handlers")

    from .app.a.a3.handlers import a_a3_handler_1

    assert a_a3_handler_1() == "a.a1.str_provider"


def test_scan_packages_with_non_existing_tag(di: PyxDI) -> None:
    di.scan(["tests.scanner.app"], tags=["non_existing_tag"])

    assert not di.providers


def test_scan_modules_tagged(di: PyxDI) -> None:
    di.register_module(AppModule)
    di.scan(["tests.scanner.app.a"], tags=["inject"])

    from .app.a.a3.handlers import a_a3_handler_1

    assert a_a3_handler_1() == "a.a1.str_provider"


def test_injectable_decorator_no_args() -> None:
    @injectable
    def my_func() -> None:
        pass

    assert getattr(my_func, "__injectable__") is True
    assert getattr(my_func, "__injectable_tags__") is None


def test_injectable_decorator_no_args_provided() -> None:
    @injectable()
    def my_func() -> None:
        pass

    assert getattr(my_func, "__injectable__") is True
    assert getattr(my_func, "__injectable_tags__") is None


def test_injectable_decorator() -> None:
    @injectable(tags=["tag1", "tag2"])
    def my_func() -> None:
        pass

    assert getattr(my_func, "__injectable__") is True
    assert getattr(my_func, "__injectable_tags__") == ["tag1", "tag2"]
