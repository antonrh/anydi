from pyxdi._decorators import request, singleton, transient  # noqa

from tests.fixtures import Service


def test_request() -> None:
    request(Service)

    assert getattr(Service, "__scope__", "request")


def test_transient() -> None:
    transient(Service)

    assert getattr(Service, "__scope__", "transient")


def test_singleton() -> None:
    singleton(Service)

    assert getattr(Service, "__scope__", "singleton")
