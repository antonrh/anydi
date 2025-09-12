"""Shared AnyDI utils module."""

from __future__ import annotations

import inspect
import re
import sys
from collections.abc import AsyncIterator, Iterator
from typing import Any, Callable, ForwardRef, TypeVar

from typing_extensions import get_args, get_origin

try:
    from types import NoneType
except ImportError:
    NoneType = type(None)


T = TypeVar("T")


def type_repr(obj: Any) -> str:
    """Get a string representation of a type or object."""
    if isinstance(obj, str):
        return obj

    # Get module and qualname with defaults to handle non-types directly
    module = getattr(obj, "__module__", type(obj).__module__)
    qualname = getattr(obj, "__qualname__", type(obj).__qualname__)

    origin = get_origin(obj)
    # If origin exists, handle generics recursively
    if origin:
        args = ", ".join(type_repr(arg) for arg in get_args(obj))
        return f"{type_repr(origin)}[{args}]"

    # Substitute standard library prefixes for clarity
    full_qualname = f"{module}.{qualname}"
    return re.sub(
        r"\b(builtins|typing|typing_extensions|collections\.abc|types)\.",
        "",
        full_qualname,
    )


def is_context_manager(obj: Any) -> bool:
    """Check if the given object is a context manager."""
    return hasattr(obj, "__enter__") and hasattr(obj, "__exit__")


def is_async_context_manager(obj: Any) -> bool:
    """Check if the given object is an async context manager."""
    return hasattr(obj, "__aenter__") and hasattr(obj, "__aexit__")


def is_none_type(tp: Any) -> bool:
    """Check if the given object is a None type."""
    return tp in (None, NoneType)


def is_iterator_type(tp: Any) -> bool:
    """Check if the given object is an iterator type."""
    return tp in (Iterator, AsyncIterator)


def get_typed_annotation(
    annotation: Any, globalns: dict[str, Any], module: Any = None
) -> Any:
    """Get the typed annotation of a callable object."""
    if isinstance(annotation, str):
        if sys.version_info >= (3, 10):
            ref = ForwardRef(annotation, module=module)
        else:
            ref = ForwardRef(annotation)
        annotation = ref._evaluate(globalns, globalns, recursive_guard=frozenset())  # noqa
    return annotation


def get_typed_parameters(obj: Callable[..., Any]) -> list[inspect.Parameter]:
    """Get the typed parameters of a callable object."""
    globalns = getattr(obj, "__globals__", {})
    module = getattr(obj, "__module__", None)
    return [
        parameter.replace(
            annotation=get_typed_annotation(
                parameter.annotation, globalns, module=module
            )
        )
        for parameter in inspect.signature(obj).parameters.values()
    ]


class _Sentinel:
    __slots__ = ("_name",)

    def __init__(self, name: str) -> None:
        self._name = name

    def __repr__(self) -> str:
        return f"<{self._name}>"

    def __eq__(self, other: object) -> bool:
        return self is other

    def __hash__(self) -> int:
        return id(self)


NOT_SET = _Sentinel("NOT_SET")


class InjectMarker:
    """A marker object for declaring injectable dependencies."""

    __slots__ = ("_interface",)

    def __init__(self, interface: Any = NOT_SET) -> None:
        self._interface = interface

    @property
    def interface(self) -> Any:
        if self._interface is NOT_SET:
            raise TypeError("Interface is not set.")
        return self._interface

    @interface.setter
    def interface(self, interface: Any) -> None:
        self._interface = interface


def is_inject_marker(obj: Any) -> bool:
    return isinstance(obj, InjectMarker)


def Inject() -> Any:
    return InjectMarker()


class Event:
    """Represents an event object."""

    __slots__ = ()


def is_event_type(obj: Any) -> bool:
    """Checks if an object is an event type."""
    return inspect.isclass(obj) and issubclass(obj, Event)
