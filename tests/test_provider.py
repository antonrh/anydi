from collections.abc import AsyncIterator, Iterator
from typing import Annotated, Any, Callable

import pytest

from anydi._provider import CallableKind, Provider
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


class TestProvider:
    @pytest.mark.parametrize(
        "call, kind, interface",
        [
            (func, CallableKind.FUNCTION, str),
            (Class, CallableKind.CLASS, Class),
            (generator, CallableKind.GENERATOR, str),
            (async_generator, CallableKind.ASYNC_GENERATOR, str),
            (coro, CallableKind.COROUTINE, str),
        ],
    )
    def test_construct(
        self, call: Callable[..., Any], kind: CallableKind, interface: Any
    ) -> None:
        provider = Provider(call=call, scope="singleton")

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
    def test_construct_interface(
        self, annotation: type[Any], expected: type[Any]
    ) -> None:
        def call() -> annotation:  # type: ignore[valid-type]
            return object()

        provider = Provider(call=call, scope="singleton")

        assert provider.interface == expected

    @pytest.mark.parametrize(
        "call, kind",
        [(event, CallableKind.GENERATOR), (async_event, CallableKind.ASYNC_GENERATOR)],
    )
    def test_construct_event(
        self,
        call: Callable[..., Any],
        kind: CallableKind,
    ) -> None:
        provider = Provider(call=call, scope="singleton")

        assert provider.kind == kind
        assert issubclass(provider.interface, Event)

    def test_construct_with_interface(self) -> None:
        provider = Provider(call=lambda: "hello", scope="singleton", interface=str)

        assert provider.interface is str

    def test_construct_with_none(self) -> None:
        with pytest.raises(TypeError) as exc_info:
            Provider(call=lambda: "hello", scope="singleton", interface=None)

        assert str(exc_info.value) == (
            "Missing `tests.test_provider.TestProvider.test_construct_with_none."
            "<locals>.<lambda>` provider return annotation."
        )

    def test_construct_provider_without_return_annotation(self) -> None:
        def provide_message():  # type: ignore[no-untyped-def]
            return "hello"

        with pytest.raises(TypeError) as exc_info:
            Provider(call=provide_message, scope="singleton")

        assert str(exc_info.value) == (
            "Missing `tests.test_provider.TestProvider.test_construct_provider_without_"
            "return_annotation.<locals>.provide_message` provider return annotation."
        )

    def test_construct_not_callable(self) -> None:
        with pytest.raises(TypeError) as exc_info:
            Provider(call="Test", scope="singleton")  # type: ignore[arg-type]

        assert str(exc_info.value) == (
            "The provider `Test` is invalid because it is not a callable object. "
            "Only callable providers are allowed."
        )

    def test_construct_iterator_no_arg_not_allowed(self) -> None:
        with pytest.raises(TypeError) as exc_info:
            Provider(call=iterator, scope="singleton")

        assert str(exc_info.value) == (
            "Cannot use `tests.test_provider.iterator` resource type annotation "
            "without actual type argument."
        )

    def test_construct_unsupported_scope(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            Provider(call=generator, scope="other")  # type: ignore[arg-type]

        assert str(exc_info.value) == (
            "The scope provided is invalid. Only the following scopes are supported: "
            "transient, singleton, request. Please use one of the supported scopes "
            "when registering a provider."
        )

    def test_construct_transient_resource_not_allowed(self) -> None:
        with pytest.raises(TypeError) as exc_info:
            Provider(call=generator, scope="transient")

        assert str(exc_info.value) == (
            "The resource provider `tests.test_provider.generator` is attempting to "
            "register with a transient scope, which is not allowed."
        )

    def test_construct_positional_only_parameter_not_allowed(self) -> None:
        def provider_message(a: int, /, b: str) -> str:
            return f"{a} {b}"

        with pytest.raises(TypeError) as exc_info:
            Provider(call=provider_message, scope="singleton")

        assert str(exc_info.value) == (
            "Positional-only parameter `a` is not allowed in the provider `tests.test_"
            "provider.TestProvider.test_construct_positional_only_parameter_not_"
            "allowed.<locals>.provider_message`."
        )
