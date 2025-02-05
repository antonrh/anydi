from collections.abc import AsyncIterator, Iterator
from typing import Annotated, Any, Callable

import pytest

from anydi._provider import ProviderKind, create_provider
from anydi._types import Event

from tests.fixtures import Service


def func() -> str:
    return "func"


class Class:
    pass


def generator() -> Iterator[str]:
    yield "generator"


async def async_generator() -> AsyncIterator[str]:
    yield "async_generator"


async def coro() -> str:
    return "coro"


def event() -> Iterator[None]:
    yield


async def async_event() -> AsyncIterator[None]:
    yield


def iterator() -> Iterator:  # type: ignore[type-arg]
    yield


@pytest.mark.parametrize(
    "call, kind, interface",
    [
        (func, ProviderKind.FUNCTION, str),
        (Class, ProviderKind.CLASS, Class),
        (generator, ProviderKind.GENERATOR, str),
        (async_generator, ProviderKind.ASYNC_GENERATOR, str),
        (coro, ProviderKind.COROUTINE, str),
    ],
)
def test_create_provider(
    call: Callable[..., Any], kind: ProviderKind, interface: Any
) -> None:
    provider = create_provider(call=call, scope="singleton")

    assert provider.kind == kind
    assert provider.interface is interface


@pytest.mark.parametrize(
    "annotation, expected",
    [
        (str, str),
        (int, int),
        (Service, Service),
        (Iterator[Service], Service),
        (AsyncIterator[Service], Service),
        (dict[str, Any], dict[str, Any]),
        (list[str], list[str]),
        ("list[str]", list[str]),
        (tuple[str, ...], tuple[str, ...]),
        ("tuple[str, ...]", tuple[str, ...]),
        ('Annotated[str, "name"]', Annotated[str, "name"]),
    ],
)
def test_create_provider_interface(annotation: type[Any], expected: type[Any]) -> None:
    def call() -> annotation:  # type: ignore[valid-type]
        return object()

    provider = create_provider(call=call, scope="singleton")

    assert provider.interface == expected


@pytest.mark.parametrize(
    "call, kind",
    [(event, ProviderKind.GENERATOR), (async_event, ProviderKind.ASYNC_GENERATOR)],
)
def test_create_provider_event(
    call: Callable[..., Any],
    kind: ProviderKind,
) -> None:
    provider = create_provider(call=call, scope="singleton")

    assert provider.kind == kind
    assert issubclass(provider.interface, Event)


def test_create_provider_with_interface() -> None:
    provider = create_provider(call=lambda: "hello", scope="singleton", interface=str)

    assert provider.interface is str


def test_create_provider_with_none() -> None:
    with pytest.raises(TypeError) as exc_info:
        create_provider(call=lambda: "hello", scope="singleton", interface=None)

    assert str(exc_info.value) == (
        "Missing `tests.test_provider.test_create_provider_with_none."
        "<locals>.<lambda>` provider return annotation."
    )


def test_create_provider_provider_without_return_annotation() -> None:
    def provide_message():  # type: ignore[no-untyped-def]
        return "hello"

    with pytest.raises(TypeError) as exc_info:
        create_provider(call=provide_message, scope="singleton")

    assert str(exc_info.value) == (
        "Missing `tests.test_provider.test_create_provider_provider_without_"
        "return_annotation.<locals>.provide_message` provider return annotation."
    )


def test_create_provider_not_callable() -> None:
    with pytest.raises(TypeError) as exc_info:
        create_provider(call="Test", scope="singleton")  # type: ignore[arg-type]

    assert str(exc_info.value) == (
        "The provider `Test` is invalid because it is not a callable object. "
        "Only callable providers are allowed."
    )


def test_create_provider_iterator_no_arg_not_allowed() -> None:
    with pytest.raises(TypeError) as exc_info:
        create_provider(call=iterator, scope="singleton")

    assert str(exc_info.value) == (
        "Cannot use `tests.test_provider.iterator` resource type annotation "
        "without actual type argument."
    )


def test_create_provider_unsupported_scope() -> None:
    with pytest.raises(ValueError) as exc_info:
        create_provider(call=generator, scope="other")  # type: ignore[arg-type]

    assert str(exc_info.value) == (
        "The provider `tests.test_provider.generator` scope is invalid. Only the "
        "following scopes are supported: transient, singleton, request. Please use "
        "one of the supported scopes when registering a provider."
    )


def test_create_provider_transient_resource_not_allowed() -> None:
    with pytest.raises(TypeError) as exc_info:
        create_provider(call=generator, scope="transient")

    assert str(exc_info.value) == (
        "The resource provider `tests.test_provider.generator` is attempting to "
        "register with a transient scope, which is not allowed."
    )


def test_create_provider_without_annotation() -> None:
    def service_ident() -> str:
        return "10000"

    def service(ident) -> Service:  # type: ignore[no-untyped-def]
        return Service(ident=ident)

    with pytest.raises(TypeError) as exc_info:
        create_provider(call=service, scope="singleton")

    assert str(exc_info.value) == (
        "Missing provider "
        "`tests.test_provider.test_create_provider_without_annotation"
        ".<locals>.service` dependency `ident` annotation."
    )


def test_create_provider_positional_only_parameter_not_allowed() -> None:
    def provider_message(a: int, /, b: str) -> str:
        return f"{a} {b}"

    with pytest.raises(TypeError) as exc_info:
        create_provider(call=provider_message, scope="singleton")

    assert str(exc_info.value) == (
        "Positional-only parameters are not allowed in the provider `tests.test_"
        "provider.test_create_provider_positional_only_parameter_not_"
        "allowed.<locals>.provider_message`."
    )
