import typing as t

import pytest

from pyxdi._base import DependencyParam, Provider, PyxDI  # noqa
from pyxdi._decorators import transient  # noqa
from pyxdi._exceptions import (  # noqa
    InvalidProviderType,
    InvalidScope,
    MissingAnnotation,
    NotSupportedAnnotation,
    ProviderAlreadyRegistered,
    ProviderNotRegistered,
    ScopeMismatch,
    UnknownDependency,
)
from pyxdi._types import Scope  # noqa

from tests.fixtures import Service


@pytest.fixture
def di() -> PyxDI:
    return PyxDI()


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
    with pytest.raises(ProviderNotRegistered):
        assert di.get_provider(str)


def test_validate_unresolved_provider_dependencies(di: PyxDI) -> None:
    def service(ident: str) -> Service:
        return Service(ident=ident)

    di.register_provider(Service, service)

    with pytest.raises(UnknownDependency) as exc_info:
        di.validate()

    assert str(exc_info.value) == (
        "Unknown provided dependencies detected:\n"
        "- `tests.test_base.test_validate_unresolved_provider_dependencies"
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
        "- `tests.test_base.test_validate_unresolved_injected_dependencies.<locals>"
        ".func1` has unknown `service: tests.fixtures.Service` injected parameter\n"
        "- `tests.test_base.test_validate_unresolved_injected_dependencies.<locals>"
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
    with pytest.raises(InvalidProviderType) as exc_info:
        di.register_provider(str, "Test")  # type: ignore[arg-type]

    assert str(exc_info.value) == (
        "Invalid provider type. Only callable providers are allowed."
    )


def test_register_provider_cannot_override(di: PyxDI) -> None:
    di.register_provider(str, lambda: "test")

    with pytest.raises(ProviderAlreadyRegistered) as exc_info:
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
        "`tests.test_base.test_register_provider_without_annotation.<locals>.service` "
        "dependency `ident` annotation."
    )


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
        "Missing `tests.test_base.test_get_provider_annotation_missing.<locals>"
        ".provider` provider return annotation."
    )


def test_get_provider_annotation_origin_without_args(di: PyxDI) -> None:
    def provider() -> list:  # type: ignore[type-arg]
        return []

    with pytest.raises(NotSupportedAnnotation) as exc_info:
        di._get_provider_annotation(provider)

    assert str(exc_info.value) == (
        "Cannot use `tests.test_base.test_get_provider_annotation_origin_without_args."
        "<locals>.provider` generic type annotation without actual type."
    )
