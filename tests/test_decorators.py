from pyxdi.core import Module
from pyxdi.decorators import provider, request, singleton, transient

from tests.fixtures import Service


def test_provider() -> None:
    class TestModule(Module):
        @provider(scope="singleton", override=True)
        def provider(self) -> str:
            return "test"

    assert getattr(TestModule.provider, "__pyxdi_provider__") == {
        "scope": "singleton",
        "override": True,
    }


def test_request() -> None:
    request(Service)

    assert getattr(Service, "__pyxdi_scope__") == "request"


def test_transient() -> None:
    transient(Service)

    assert getattr(Service, "__pyxdi_scope__") == "transient"


def test_singleton() -> None:
    singleton(Service)

    assert getattr(Service, "__pyxdi_scope__") == "singleton"
