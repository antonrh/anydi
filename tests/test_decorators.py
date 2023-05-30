from pyxdi.decorators import inject, provider, request, singleton, transient

from tests.fixtures import Service


def test_request() -> None:
    request(Service)

    assert getattr(Service, "__pyxdi_scope__") == "request"


def test_transient() -> None:
    transient(Service)

    assert getattr(Service, "__pyxdi_scope__") == "transient"


def test_singleton() -> None:
    singleton(Service)

    assert getattr(Service, "__pyxdi_scope__") == "singleton"


def test_provider_no_args() -> None:
    @provider
    def service_provider() -> str:
        return "test"

    assert getattr(service_provider, "__pyxdi_provider__") == {
        "scope": None,
        "override": None,
    }


def test_provider_no_args_provided() -> None:
    @provider()
    def service_provider() -> str:
        return "test"

    assert getattr(service_provider, "__pyxdi_provider__") == {
        "scope": None,
        "override": None,
    }


def test_provider() -> None:
    @provider(scope="singleton", override=True)
    def service_provider() -> str:
        return "test"

    assert getattr(service_provider, "__pyxdi_provider__") == {
        "scope": "singleton",
        "override": True,
    }


def test_inject_no_args() -> None:
    @inject
    def my_func() -> None:
        pass

    assert getattr(my_func, "__pyxdi_inject__") is True
    assert getattr(my_func, "__pyxdi_tags__") is None


def test_inject_no_args_provided() -> None:
    @inject()
    def my_func() -> None:
        pass

    assert getattr(my_func, "__pyxdi_inject__") is True
    assert getattr(my_func, "__pyxdi_tags__") is None


def test_inject() -> None:
    @inject(tags=["tag1", "tag2"])
    def my_func() -> None:
        pass

    assert getattr(my_func, "__pyxdi_inject__") is True
    assert getattr(my_func, "__pyxdi_tags__") == ["tag1", "tag2"]
