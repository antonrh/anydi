from typing import Iterator

import pytest

from pyxdi._core import DI, Binding  # noqa
from pyxdi._exceptions import InvalidScope, ProviderAlreadyBound

from tests.fixtures import Service


@pytest.fixture
def di() -> DI:
    return DI()


def test_has_binding(di: DI) -> None:
    di.bind(str, lambda: "test")

    assert di.has_binding(str)


def test_get_binding(di: DI) -> None:
    def provider() -> str:
        return "test"

    di.bind(str, provider, scope="singleton")

    assert di.get_binding(str) == Binding(dependency=provider, scope="singleton")


def test_get_binding_not_found(di: DI) -> None:
    with pytest.raises(LookupError):
        assert di.get_binding(Service)


def test_bind_invalid_scope(di: DI) -> None:
    with pytest.raises(InvalidScope) as exc_info:
        di.bind(str, lambda: "test", scope="invalid")  # type: ignore[arg-type]

    assert str(exc_info.value) == "Invalid scope."


def test_bind_singleton_scoped_and_get_instance(di: DI) -> None:
    ident = "test"

    def provider() -> Service:
        return Service(ident=ident)

    di.bind(Service, provider, scope="singleton")

    service = di.get(Service)

    assert service.ident == ident

    assert di.get(Service) is service


def test_bind_transient_scoped_and_get_instance(di: DI) -> None:
    ident = "test"

    def provider() -> Service:
        return Service(ident=ident)

    di.bind(Service, provider, scope="transient")

    service = di.get(Service)

    assert service.ident == ident
    assert not di.get(Service) is service


def test_bind_request_scoped_and_get_instance(di: DI) -> None:
    ident = "test"

    def provider() -> Service:
        return Service(ident=ident)

    di.bind(Service, provider, scope="request")

    with di.request_context():
        service = di.get(Service)

        assert service.ident == ident
        assert di.get(Service) is service

    with di.request_context():
        assert not di.get(Service) is service


def test_bind_request_scoped_not_started(di: DI) -> None:
    ident = "test"

    def provider() -> Service:
        return Service(ident=ident)

    di.bind(Service, provider, scope="request")

    with pytest.raises(LookupError) as exc_info:
        di.get(Service)

    assert str(exc_info.value) == "Request context is not started."


def test_bind_cannot_override(di: DI) -> None:
    di.bind(str, lambda: "test")

    with pytest.raises(ProviderAlreadyBound) as exc_info:
        di.bind(str, lambda: "other", override=False)

    assert str(exc_info.value) == "Provider interface `str` already bound."


def test_bind_override(di: DI) -> None:
    di.bind(str, lambda: "test")
    di.bind(str, lambda: "other", override=True)

    assert di.get(str) == "other"


def test_bind_transient_scoped_generator_provider(di: DI) -> None:
    ident = "test"

    def provider() -> Iterator[Service]:
        service = Service(ident=ident)
        service.events.append("before")
        yield service
        service.events.append("after")

    di.bind(Service, provider, scope="transient")

    service = di.get(Service)

    assert service.ident == "test"
    assert service.events == ["before", "after"]
