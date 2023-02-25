import typing as t
from dataclasses import dataclass

import pytest

from pyxdi.core import DependencyParam, Provider, PyxDI
from pyxdi.exceptions import (
    InvalidScope,
    MissingAnnotation,
    NotSupportedAnnotation,
    ProviderError,
    ScopeMismatch,
    UnknownDependency,
)
from pyxdi.types import Scope

from tests.fixtures import Service


@pytest.fixture
def di() -> PyxDI:
    return PyxDI()


def test_start_and_close(di: PyxDI) -> None:
    events = []

    def dep1() -> t.Iterator[str]:
        events.append("dep1:before")
        yield "test"
        events.append("dep1:after")

    di.register_provider(str, dep1, scope="singleton")

    di.start()

    assert di.get(str) == "test"

    di.close()

    assert events == ["dep1:before", "dep1:after"]


def test_has_provider(di: PyxDI) -> None:
    di.register_provider(str, lambda: "test")

    assert di.has_provider(str)


def test_have_not_provider(di: PyxDI) -> None:
    assert not di.has_provider(str)


def test_get_provider(di: PyxDI) -> None:
    def func() -> str:
        return "test"

    di.register_provider(str, func, scope="singleton")

    assert di.get_provider(str) == Provider(obj=func, scope="singleton")


def test_get_provider_not_registered(di: PyxDI) -> None:
    with pytest.raises(ProviderError):
        assert di.get_provider(str)


def test_validate_unresolved_provider_dependencies(di: PyxDI) -> None:
    def service(ident: str) -> Service:
        return Service(ident=ident)

    di.register_provider(Service, service)

    with pytest.raises(UnknownDependency) as exc_info:
        di.validate()

    assert str(exc_info.value) == (
        "Unknown provided dependencies detected:\n"
        "- `tests.test_core.test_validate_unresolved_provider_dependencies"
        ".<locals>.service` has unknown `ident: str` parameter."
    )


def test_validate_unresolved_injected_dependencies(di: PyxDI) -> None:
    def func1(service: Service = DependencyParam()) -> None:
        return None

    def func2(message: str = DependencyParam()) -> None:
        return None

    di.inject(func1)
    di.inject(func2)

    with pytest.raises(UnknownDependency) as exc_info:
        di.validate()

    assert str(exc_info.value) == (
        "Unknown injected dependencies detected:\n"
        "- `tests.test_core.test_validate_unresolved_injected_dependencies.<locals>"
        ".func1` has unknown `service: tests.fixtures.Service` injected parameter\n"
        "- `tests.test_core.test_validate_unresolved_injected_dependencies.<locals>"
        ".func2` has unknown `message: str` injected parameter."
    )


@pytest.mark.parametrize(
    "scope1, scope2, scope3, valid",
    [
        (None, None, None, True),
        ("transient", "transient", "transient", True),
        ("transient", "transient", "singleton", True),
        ("transient", "transient", "request", True),
        ("transient", "singleton", "transient", False),
        ("transient", "singleton", "singleton", True),
        ("transient", "singleton", "request", False),
        ("transient", "request", "transient", False),
        ("transient", "request", "singleton", True),
        ("transient", "request", "request", True),
        ("singleton", "transient", "transient", False),
        ("singleton", "transient", "singleton", False),
        ("singleton", "transient", "request", False),
        ("singleton", "singleton", "transient", False),
        ("singleton", "singleton", "singleton", True),
        ("singleton", "singleton", "request", False),
        ("singleton", "request", "transient", False),
        ("singleton", "request", "singleton", False),
        ("singleton", "request", "request", False),
        ("request", "transient", "transient", False),
        ("request", "transient", "singleton", False),
        ("request", "transient", "request", False),
        ("request", "singleton", "transient", False),
        ("request", "singleton", "singleton", True),
        ("request", "singleton", "request", False),
        ("request", "request", "transient", False),
        ("request", "request", "singleton", True),
        ("request", "request", "request", True),
    ],
)
def test_register_provider_allowed_scopes(
    di: PyxDI, scope1: Scope, scope2: Scope, scope3: Scope, valid: bool
) -> None:
    def mixed(a: int, b: float) -> str:
        return f"{a} * {b} = {a * b}"

    def a() -> int:
        return 2

    def b(a: int) -> float:
        return a * 2.5

    try:
        di.register_provider(str, mixed, scope=scope1)
        di.register_provider(int, a, scope=scope3)
        di.register_provider(float, b, scope=scope2)
    except ScopeMismatch:
        result = False
    else:
        result = True

    assert result == valid


def test_register_provider_invalid_scope(di: PyxDI) -> None:
    with pytest.raises(InvalidScope) as exc_info:
        di.register_provider(
            str,
            lambda: "test",
            scope="invalid",  # type: ignore[arg-type]
        )

    assert str(exc_info.value) == (
        "Invalid scope. Only transient, singleton, request scope are supported."
    )


def test_register_invalid_provider_type(di: PyxDI) -> None:
    with pytest.raises(ProviderError) as exc_info:
        di.register_provider(str, "Test")  # type: ignore[arg-type]

    assert str(exc_info.value) == (
        "Invalid provider `Test` type. Only callable providers are allowed."
    )


def test_register_provider_cannot_override(di: PyxDI) -> None:
    di.register_provider(str, lambda: "test")

    with pytest.raises(ProviderError) as exc_info:
        di.register_provider(str, lambda: "other", override=False)

    assert str(exc_info.value) == "Provider interface `str` already registered."


def test_register_provider_with_override(di: PyxDI) -> None:
    di.register_provider(str, lambda: "test")
    di.register_provider(str, lambda: "other", override=True)

    assert di.get(str) == "other"


def test_register_provider_without_annotation(di: PyxDI) -> None:
    def service_ident() -> str:
        return "10000"

    def service(ident) -> Service:  # type: ignore[no-untyped-def]
        return Service(ident=ident)

    di.register_provider(str, service_ident)

    with pytest.raises(MissingAnnotation) as exc_info:
        di.register_provider(Service, service)

    assert str(exc_info.value) == (
        "Missing provider "
        "`tests.test_core.test_register_provider_without_annotation.<locals>.service` "
        "dependency `ident` annotation."
    )


def test_register_transient_scoped_generator_provider(di: PyxDI) -> None:
    ident = "test"

    def provider() -> t.Iterator[Service]:
        service = Service(ident=ident)
        service.events.append("before")
        yield service
        service.events.append("after")

    di.register_provider(Service, provider, scope="transient")

    di.start()

    service = di.get(Service)

    assert service.ident == "test"
    assert service.events == ["before", "after"]


def test_register_singleton_scoped_provider_and_get_instance(di: PyxDI) -> None:
    ident = "test"

    def provider() -> Service:
        return Service(ident=ident)

    di.register_provider(Service, provider, scope="singleton")

    service = di.get(Service)

    assert service.ident == ident

    assert di.get(Service) is service


def test_register_transient_scoped_provider_and_get_instance(di: PyxDI) -> None:
    ident = "test"

    def provider() -> Service:
        return Service(ident=ident)

    di.register_provider(Service, provider, scope="transient")

    service = di.get(Service)

    assert service.ident == ident
    assert not di.get(Service) is service


def test_register_request_scoped_provider_and_get_instance(di: PyxDI) -> None:
    ident = "test"

    def provider() -> Service:
        return Service(ident=ident)

    di.register_provider(Service, provider, scope="request")

    with di.request_context():
        service = di.get(Service)

        assert service.ident == ident
        assert di.get(Service) is service

    with di.request_context():
        assert not di.get(Service) is service


def test_get_request_scoped_not_started(di: PyxDI) -> None:
    ident = "test"

    def provider() -> Service:
        return Service(ident=ident)

    di.register_provider(Service, provider, scope="request")

    with pytest.raises(LookupError) as exc_info:
        di.get(Service)

    assert str(exc_info.value) == "Request context is not started."


def test_get_and_set_with_request_context(di: PyxDI) -> None:
    def service(ident: str) -> Service:
        return Service(ident=ident)

    di.register_provider(Service, service, scope="request")

    with di.request_context() as ctx:
        ctx.set(str, "test")

        assert di.get(Service).ident == "test"


def test_auto_registered_dependency(di: PyxDI) -> None:
    di._auto_register = True

    @di.provider(scope="transient")
    def ident() -> str:
        return "test"

    @dataclass
    class Component:
        __scope__: t.ClassVar[str] = "transient"

        ident: str

    @di.inject
    def func(component: Component = DependencyParam()) -> str:
        return component.ident

    result = func()

    assert result == "test"


@pytest.mark.parametrize(
    "annotation, expected",
    [
        (str, str),
        (int, int),
        (Service, Service),
        (t.Iterator[Service], Service),
        (t.AsyncIterator[Service], Service),
        (t.Dict[str, t.Any], t.Dict[str, t.Any]),
        (t.List[str], t.List[str]),
        (t.Tuple[str, ...], t.Tuple[str, ...]),
    ],
)
def test_get_supported_provider_annotation(
    di: PyxDI, annotation: t.Type[t.Any], expected: t.Type[t.Any]
) -> None:
    def provider() -> annotation:  # type: ignore[valid-type]
        return object()

    assert di._get_provider_annotation(provider) == expected


def test_get_provider_annotation_missing(di: PyxDI) -> None:
    def provider():  # type: ignore[no-untyped-def]
        return object()

    with pytest.raises(MissingAnnotation) as exc_info:
        di._get_provider_annotation(provider)

    assert str(exc_info.value) == (
        "Missing `tests.test_core.test_get_provider_annotation_missing.<locals>"
        ".provider` provider return annotation."
    )


def test_get_provider_annotation_origin_without_args(di: PyxDI) -> None:
    def provider() -> list:  # type: ignore[type-arg]
        return []

    with pytest.raises(NotSupportedAnnotation) as exc_info:
        di._get_provider_annotation(provider)

    assert str(exc_info.value) == (
        "Cannot use `tests.test_core.test_get_provider_annotation_origin_without_args."
        "<locals>.provider` generic type annotation without actual type."
    )


def test_get_injectable_params_missing_annotation(di: PyxDI) -> None:
    def func(name=DependencyParam()) -> str:  # type: ignore[no-untyped-def]
        return name  # type: ignore[no-any-return]

    with pytest.raises(MissingAnnotation) as exc_info:
        di.inject(func)

    assert str(exc_info.value) == (
        "Missing `tests.test_core.test_get_injectable_params_missing_annotation"
        ".<locals>.func` parameter annotation."
    )


def test_get_injectable_params(di: PyxDI) -> None:
    @di.provider
    def ident() -> str:
        return "1000"

    @di.provider
    def service(ident: str) -> Service:
        return Service(ident=ident)

    @di.inject
    def func(name: str, service: Service = DependencyParam()) -> str:
        return f"{name} = {service.ident}"

    result = func(name="service ident")

    assert result == "service ident = 1000"


def test_get_provider_arguments(di: PyxDI) -> None:
    def a() -> int:
        return 10

    def b() -> float:
        return 1.0

    def c() -> str:
        return "test"

    def service(a: int, /, b: float, *, c: str) -> Service:
        return Service(ident=f"{a}/{b}/{c}")

    di.register_provider(int, a)
    di.register_provider(float, b)
    di.register_provider(str, c)
    provider = di.register_provider(Service, service)

    args, kwargs = di._get_provider_arguments(provider)

    assert args == [10]
    assert kwargs == {"b": 1.0, "c": "test"}
