from __future__ import annotations

import inspect
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from enum import IntEnum
from functools import cached_property
from typing import Any, Callable

from typing_extensions import get_args, get_origin

try:
    from types import NoneType
except ImportError:
    NoneType = type(None)  # type: ignore[misc]


from ._types import Event, Scope
from ._utils import get_full_qualname, get_typed_annotation

_sentinel = object()


class ProviderKind(IntEnum):
    CLASS = 1
    FUNCTION = 2
    COROUTINE = 3
    GENERATOR = 4
    ASYNC_GENERATOR = 5


@dataclass(kw_only=True, frozen=True)
class Provider:
    call: Callable[..., Any]
    scope: Scope
    interface: Any
    name: str
    parameters: list[inspect.Parameter]
    kind: ProviderKind

    def __str__(self) -> str:
        return self.name

    @cached_property
    def is_class(self) -> bool:
        return self.kind == ProviderKind.CLASS

    @cached_property
    def is_coroutine(self) -> bool:
        return self.kind == ProviderKind.COROUTINE

    @cached_property
    def is_generator(self) -> bool:
        return self.kind == ProviderKind.GENERATOR

    @cached_property
    def is_async_generator(self) -> bool:
        return self.kind == ProviderKind.ASYNC_GENERATOR

    @cached_property
    def is_async(self) -> bool:
        return self.is_coroutine or self.is_async_generator

    @cached_property
    def is_resource(self) -> bool:
        return self.is_generator or self.is_async_generator


def create_provider(
    call: Callable[..., Any], *, scope: Scope, interface: Any = _sentinel
) -> Provider:
    name = get_full_qualname(call)

    # Detect the kind of callable provider
    kind = _detect_provider_kind(call)

    # Validate the scope of the provider
    _validate_scope(
        name, scope, kind in {ProviderKind.GENERATOR, ProviderKind.ASYNC_GENERATOR}
    )

    # Get the signature
    globalns = getattr(call, "__globals__", {})
    signature = inspect.signature(call, globals=globalns)

    # Detect the interface
    interface = _detect_interface(
        name, kind, call, interface, signature, globalns=globalns
    )

    # Detect the parameters
    parameters = _detect_provider_parameters(name, signature, globalns=globalns)

    return Provider(
        call=call,
        scope=scope,
        interface=interface,
        name=name,
        kind=kind,
        parameters=parameters,
    )


def _validate_scope(name: str, scope: Scope, is_resource: bool) -> None:
    """Validate the scope of the provider."""
    if scope not in get_args(Scope):
        raise ValueError(
            "The scope provided is invalid. Only the following scopes are "
            f"supported: {', '.join(get_args(Scope))}. Please use one of the "
            "supported scopes when registering a provider."
        )
    if is_resource and scope == "transient":
        raise TypeError(
            f"The resource provider `{name}` is attempting to register "
            "with a transient scope, which is not allowed."
        )


def _detect_provider_kind(call: Callable[..., Any]) -> ProviderKind:
    """Detect the kind of callable provider."""
    if inspect.isclass(call):
        return ProviderKind.CLASS
    elif inspect.iscoroutinefunction(call):
        return ProviderKind.COROUTINE
    elif inspect.isasyncgenfunction(call):
        return ProviderKind.ASYNC_GENERATOR
    elif inspect.isgeneratorfunction(call):
        return ProviderKind.GENERATOR
    elif inspect.isfunction(call) or inspect.ismethod(call):
        return ProviderKind.FUNCTION
    raise TypeError(
        f"The provider `{call}` is invalid because it is not a callable "
        "object. Only callable providers are allowed."
    )


def _detect_interface(
    name: str,
    kind: ProviderKind,
    call: Callable[..., Any],
    interface: Any,
    signature: inspect.Signature,
    globalns: dict[str, Any],
) -> Any:
    """Detect the interface of callable provider."""
    # If the callable is a class, return the class itself
    if kind == ProviderKind.CLASS:
        return call

    if interface is _sentinel:
        interface = signature.return_annotation
        if interface is inspect.Signature.empty:
            interface = None
        else:
            interface = get_typed_annotation(interface, globalns)

    # If the callable is an iterator, return the actual type
    iterator_types = {Iterator, AsyncIterator}
    if interface in iterator_types or get_origin(interface) in iterator_types:
        if args := get_args(interface):
            interface = args[0]
            # If the callable is a generator, return the resource type
            if interface is NoneType or interface is None:
                return type(f"Event_{uuid.uuid4().hex}", (Event,), {})
        else:
            raise TypeError(
                f"Cannot use `{name}` resource type annotation "
                "without actual type argument."
            )

    # None interface is not allowed
    if interface in {None, NoneType}:
        raise TypeError(f"Missing `{name}` provider return annotation.")

    # Set the interface
    return interface


def _detect_provider_parameters(
    name: str, signature: inspect.Signature, globalns: dict[str, Any]
) -> list[inspect.Parameter]:
    """Detect the parameters of the callable provider."""
    parameters = []
    for parameter in signature.parameters.values():
        if parameter.annotation is inspect.Parameter.empty:
            raise TypeError(
                f"Missing provider `{name}` "
                f"dependency `{parameter.name}` annotation."
            )
        if parameter.kind == inspect.Parameter.POSITIONAL_ONLY:
            raise TypeError(
                f"Positional-only parameters are not allowed in the provider `{name}`."
            )
        annotation = get_typed_annotation(parameter.annotation, globalns)
        parameters.append(parameter.replace(annotation=annotation))
    return parameters
