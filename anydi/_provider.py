from __future__ import annotations

import inspect
import uuid
from collections.abc import AsyncIterator, Iterator
from enum import IntEnum
from typing import Any, Callable, get_args

from typing_extensions import get_origin

try:
    from types import NoneType
except ImportError:
    NoneType = type(None)  # type: ignore[misc]


from ._types import Event, Scope, is_event_type
from ._utils import get_full_qualname, get_typed_annotation

_sentinel = object()


class CallableKind(IntEnum):
    CLASS = 1
    FUNCTION = 2
    COROUTINE = 3
    GENERATOR = 4
    ASYNC_GENERATOR = 5


class Provider:
    __slots__ = (
        "_call",
        "_scope",
        "_qualname",
        "_kind",
        "_interface",
        "_signature",
        "_parameters",
        "_call_module",
        "_call_globals",
    )

    def __init__(
        self, *, call: Callable[..., Any], scope: Scope, interface: Any = _sentinel
    ) -> None:
        self._call = call
        self._call_module = getattr(call, "__module__", None)
        self._call_globals = getattr(call, "__globals__", {})
        self._scope = scope
        self._qualname = get_full_qualname(call)

        # Detect the kind of callable provider
        self._detect_kind()

        # Validate the scope of the provider
        self._validate_scope()

        # Get the signature
        self._signature = inspect.signature(call)

        # Detect the interface
        self._detect_interface(interface)

        # Detect the parameters
        self._detect_parameters()

    def __str__(self) -> str:
        return self._qualname

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Provider):
            return NotImplemented
        return (
            self._call == other._call
            and self._scope == other._scope
            and self._interface == other._interface
        )

    @property
    def call(self) -> Callable[..., Any]:
        return self._call

    @property
    def kind(self) -> CallableKind:
        return self._kind

    @property
    def scope(self) -> Scope:
        return self._scope

    @property
    def interface(self) -> Any:
        return self._interface

    @property
    def parameters(self) -> list[inspect.Parameter]:
        return self._parameters

    @property
    def is_resource(self) -> bool:
        """Check if the provider is a resource."""
        return self._kind in {
            CallableKind.GENERATOR,
            CallableKind.ASYNC_GENERATOR,
        }

    @property
    def is_event(self) -> bool:
        """Check if the provider is an event."""
        return is_event_type(self._interface)

    def _validate_scope(self) -> None:
        """Validate the scope of the provider."""
        if self.is_resource and self.scope == "transient":
            raise TypeError(
                f"The resource provider `{self}` is attempting to register "
                "with a transient scope, which is not allowed."
            )

    def _detect_kind(self) -> None:
        """Detect the kind of callable provider."""
        if inspect.isclass(self.call):
            self._kind = CallableKind.CLASS
        elif inspect.iscoroutinefunction(self.call):
            self._kind = CallableKind.COROUTINE
        elif inspect.isasyncgenfunction(self.call):
            self._kind = CallableKind.ASYNC_GENERATOR
        elif inspect.isgeneratorfunction(self.call):
            self._kind = CallableKind.GENERATOR
        elif inspect.isfunction(self.call) or inspect.ismethod(self.call):
            self._kind = CallableKind.FUNCTION
        else:
            raise TypeError(
                f"The provider `{self.call}` is invalid because it is not a callable "
                "object. Only callable providers are allowed."
            )

    def _detect_interface(self, interface: Any) -> None:
        """Detect the interface of callable provider."""
        # If the callable is a class, return the class itself
        if self._kind == CallableKind.CLASS:
            self._interface = self._call
            return

        if interface is _sentinel:
            interface = self._resolve_interface(interface)

        # If the callable is an iterator, return the actual type
        if get_origin(interface) in {Iterator, AsyncIterator}:
            if args := get_args(interface):
                interface = args[0]
                # If the callable is a generator, return the resource type
                if interface is NoneType or interface is None:
                    self._interface = type(f"Event_{uuid.uuid4().hex}", (Event,), {})
                    return
            else:
                raise TypeError(
                    f"Cannot use `{self}` resource type annotation "
                    "without actual type argument."
                )

        # None interface is not allowed
        if interface in {None, NoneType}:
            raise TypeError(f"Missing `{self}` provider return annotation.")

        # Set the interface
        self._interface = interface

    def _resolve_interface(self, interface: Any) -> Any:
        """Resolve the interface of the callable provider."""
        interface = self._signature.return_annotation
        if interface is inspect._empty:  # noqa
            return None
        return get_typed_annotation(
            interface,
            self._call_globals,
            module=self._call_module,
        )

    def _detect_parameters(self) -> None:
        """Detect the parameters of the callable provider."""
        self._parameters = [
            parameter.replace(
                annotation=get_typed_annotation(
                    parameter.annotation,
                    self._call_globals,
                    module=self._call_module,
                )
            )
            for name, parameter in self._signature.parameters.items()
        ]
