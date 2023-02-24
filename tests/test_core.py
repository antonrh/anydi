import typing as t
from dataclasses import dataclass

import pytest

from pyxdi._base import DependencyParam  # noqa
from pyxdi._core import Binding, DIContext  # noqa
from pyxdi._decorators import transient  # noqa
from pyxdi._exceptions import (  # noqa
    BindingDoesNotExist,
    InvalidProviderType,
    InvalidScope,
    MissingAnnotation,
    NotSupportedAnnotation,
    ProviderAlreadyRegistered,
    ScopeMismatch,
    UnknownDependency,
)
from pyxdi._types import Scope  # noqa

from tests.fixtures import Service


@pytest.fixture
def di_context() -> DIContext:
    return DIContext()


def test_autobind_dependency() -> None:
    di_context = DIContext(autobind=True)

    @di_context.provide(scope="transient")
    def ident() -> str:
        return "test"

    @transient
    @dataclass
    class Component:
        ident: str

    @di_context.inject_callable
    def func(component: Component = DependencyParam()) -> str:
        return component.ident

    result = func()

    assert result == "test"


def test_bind_transient_scoped_generator_provider(di_context: DIContext) -> None:
    ident = "test"

    def provider() -> t.Iterator[Service]:
        service = Service(ident=ident)
        service.events.append("before")
        yield service
        service.events.append("after")

    di_context.bind(Service, provider, scope="transient")

    service = di_context.get(Service)

    assert service.ident == "test"
    assert service.events == ["before", "after"]


def test_bind_singleton_scoped_and_get_instance(di_context: DIContext) -> None:
    ident = "test"

    def provider() -> Service:
        return Service(ident=ident)

    di_context.bind(Service, provider, scope="singleton")

    service = di_context.get(Service)

    assert service.ident == ident

    assert di_context.get(Service) is service


def test_bind_transient_scoped_and_get_instance(di_context: DIContext) -> None:
    ident = "test"

    def provider() -> Service:
        return Service(ident=ident)

    di_context.bind(Service, provider, scope="transient")

    service = di_context.get(Service)

    assert service.ident == ident
    assert not di_context.get(Service) is service


def test_bind_request_scoped_and_get_instance(di_context: DIContext) -> None:
    ident = "test"

    def provider() -> Service:
        return Service(ident=ident)

    di_context.bind(Service, provider, scope="request")

    with di_context.request_context():
        service = di_context.get(Service)

        assert service.ident == ident
        assert di_context.get(Service) is service

    with di_context.request_context():
        assert not di_context.get(Service) is service


def test_get_request_scoped_not_started(di_context: DIContext) -> None:
    ident = "test"

    def provider() -> Service:
        return Service(ident=ident)

    di_context.bind(Service, provider, scope="request")

    with pytest.raises(LookupError) as exc_info:
        di_context.get(Service)

    assert str(exc_info.value) == "Request context is not started."


def test_get_and_set_with_request_context(di_context: DIContext) -> None:
    @di_context.provide(scope="request")
    def service(ident: str) -> Service:
        return Service(ident=ident)

    with di_context.request_context() as ctx:
        ctx.set(str, "test")

        assert di_context.get(Service).ident == "test"


def test_get_provider_arguments(di_context: DIContext) -> None:
    @di_context.provide()
    def a() -> int:
        return 10

    @di_context.provide()
    def b() -> float:
        return 1.0

    @di_context.provide()
    def c() -> str:
        return "test"

    @di_context.provide()
    def service(a: int, /, b: float, *, c: str) -> Service:
        ident = f"{a}/{b}/{c}"
        return Service(ident=ident)

    assert di_context.get(Service).ident == "10/1.0/test"
