import typing as t
from dataclasses import dataclass

import pytest

from pyxdi._core import Binding, DependencyParam, DIContext  # noqa
from pyxdi._decorators import transient  # noqa
from pyxdi._exceptions import (  # noqa
    BindingDoesNotExist,
    InvalidMode,
    InvalidProviderType,
    InvalidScope,
    MissingAnnotation,
    NotSupportedAnnotation,
    ProviderAlreadyBound,
    ScopeMismatch,
    UnknownDependency,
)
from pyxdi._types import Scope  # noqa

from tests.fixtures import Service


@pytest.fixture
def di_context() -> DIContext:
    return DIContext()


def test_has_binding(di_context: DIContext) -> None:
    di_context.bind(str, lambda: "test")

    assert di_context.has_binding(str)


def test_get_binding(di_context: DIContext) -> None:
    def provider() -> str:
        return "test"

    di_context.bind(str, provider, scope="singleton")

    assert di_context.get_binding(str) == Binding(provider=provider, scope="singleton")


def test_get_binding_not_found(di_context: DIContext) -> None:
    with pytest.raises(BindingDoesNotExist):
        assert di_context.get_binding(Service)


def test_validate_unresolved_provider_dependencies(di_context: DIContext) -> None:
    def service(ident: str) -> Service:
        return Service(ident=ident)

    di_context.bind(Service, service)

    with pytest.raises(UnknownDependency) as exc_info:
        di_context.validate()

    assert str(exc_info.value) == (
        "Unknown provided dependencies detected:\n"
        "- `tests.test_core.test_validate_unresolved_provider_dependencies"
        ".<locals>.service` has unknown `ident: str` parameter."
    )


def test_validate_unresolved_injected_dependencies(di_context: DIContext) -> None:
    def func1(service: Service = DependencyParam()) -> None:
        return None

    def func2(message: str = DependencyParam()) -> None:
        return None

    di_context.inject_callable(func1)
    di_context.inject_callable(func2)

    with pytest.raises(UnknownDependency) as exc_info:
        di_context.validate()

    assert str(exc_info.value) == (
        "Unknown injected dependencies detected:\n"
        "- `tests.test_core.test_validate_unresolved_injected_dependencies.<locals>"
        ".func1` has unknown `service: tests.fixtures.Service` injected parameter\n"
        "- `tests.test_core.test_validate_unresolved_injected_dependencies.<locals>"
        ".func2` has unknown `message: str` injected parameter."
    )


def test_bind_invalid_scope(di_context: DIContext) -> None:
    with pytest.raises(InvalidScope) as exc_info:
        di_context.bind(str, lambda: "test", scope="invalid")  # type: ignore[arg-type]

    assert str(exc_info.value) == (
        "Invalid scope. Only transient, singleton, request scope are supported."
    )


def test_bind_invalid_mode(di_context: DIContext) -> None:
    async def provider() -> str:
        return "test"

    with pytest.raises(InvalidMode) as exc_info:
        di_context.bind(str, provider)

    assert str(exc_info.value) == (
        "Cannot bind asynchronous provider "
        "`tests.test_core.test_bind_invalid_mode.<locals>.provider` in `sync` mode."
    )


def test_bind_invalid_provider_type(di_context: DIContext) -> None:
    with pytest.raises(InvalidProviderType) as exc_info:
        di_context.bind(str, "Test")  # type: ignore[arg-type]

    assert str(exc_info.value) == (
        "Invalid provider type. Only callable providers are allowed."
    )


def test_bind_cannot_override(di_context: DIContext) -> None:
    di_context.bind(str, lambda: "test")

    with pytest.raises(ProviderAlreadyBound) as exc_info:
        di_context.bind(str, lambda: "other", override=False)

    assert str(exc_info.value) == "Provider interface `str` already bound."


def test_bind_override(di_context: DIContext) -> None:
    di_context.bind(str, lambda: "test")
    di_context.bind(str, lambda: "other", override=True)

    assert di_context.get(str) == "other"


def test_bind_provider_without_annotation(di_context: DIContext) -> None:
    def service_ident() -> str:
        return "10000"

    def service(ident) -> Service:  # type: ignore[no-untyped-def]
        return Service(ident=ident)

    di_context.bind(str, service_ident)

    with pytest.raises(MissingAnnotation) as exc_info:
        di_context.bind(Service, service)

    assert str(exc_info.value) == (
        "Missing provider "
        "`tests.test_core.test_bind_provider_without_annotation.<locals>.service` "
        "dependency `ident` annotation."
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
def test_bind_allowed_scopes(
    di_context: DIContext, scope1: Scope, scope2: Scope, scope3: Scope, valid: bool
) -> None:
    def mixed(a: int, b: float) -> str:
        return f"{a} * {b} = {a * b}"

    def a() -> int:
        return 2

    def b(a: int) -> float:
        return a * 2.5

    try:
        di_context.bind(str, mixed, scope=scope1)
        di_context.bind(int, a, scope=scope3)
        di_context.bind(float, b, scope=scope2)
    except ScopeMismatch:
        result = False
    else:
        result = True

    assert result == valid


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
    di_context: DIContext, annotation: t.Type[t.Any], expected: t.Type[t.Any]
) -> None:
    def provider() -> annotation:  # type: ignore[valid-type]
        return object()

    assert di_context.get_provider_annotation(provider) == expected


def test_get_provider_annotation_missing(di_context: DIContext) -> None:
    def provider():  # type: ignore[no-untyped-def]
        return object()

    with pytest.raises(MissingAnnotation) as exc_info:
        di_context.get_provider_annotation(provider)

    assert str(exc_info.value) == (
        "Missing `tests.test_core.test_get_provider_annotation_missing.<locals>"
        ".provider` provider return annotation."
    )


def test_get_provider_annotation_origin_without_args(di_context: DIContext) -> None:
    def provider() -> list:  # type: ignore[type-arg]
        return []

    with pytest.raises(NotSupportedAnnotation) as exc_info:
        di_context.get_provider_annotation(provider)

    assert str(exc_info.value) == (
        "Cannot use `tests.test_core.test_get_provider_annotation_origin_without_args."
        "<locals>.provider` generic type annotation without actual type."
    )


def test_get_injectable_params_missing_annotation(di_context: DIContext) -> None:
    def func(name=DependencyParam()) -> str:  # type: ignore[no-untyped-def]
        return name  # type: ignore[no-any-return]

    with pytest.raises(MissingAnnotation) as exc_info:
        di_context.inject_callable(func)

    assert str(exc_info.value) == (
        "Missing `tests.test_core.test_get_injectable_params_missing_annotation"
        ".<locals>.func` parameter annotation."
    )


def test_get_injectable_params(di_context: DIContext) -> None:
    @di_context.provide()
    def ident() -> str:
        return "1000"

    @di_context.provide()
    def service(ident: str) -> Service:
        return Service(ident=ident)

    @di_context.inject_callable
    def func(name: str, service: Service = DependencyParam()) -> str:
        return f"{name} = {service.ident}"

    result = func(name="service ident")

    assert result == "service ident = 1000"


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


def test_close(di_context: DIContext) -> None:
    events = []

    def dep1() -> t.Iterator[str]:
        events.append("dep1:before")
        yield "test"
        events.append("dep1:after")

    di_context.bind(str, dep1, scope="singleton")

    assert di_context.get(str) == "test"

    di_context.close()

    assert events == ["dep1:before", "dep1:after"]


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
