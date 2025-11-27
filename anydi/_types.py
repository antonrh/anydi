"""Shared AnyDI utils module."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Iterator
from types import NoneType
from typing import TYPE_CHECKING, Annotated, Any, Literal, TypeVar, get_args, get_origin

from typing_extensions import Sentinel

T = TypeVar("T")

Scope = Literal["transient", "singleton", "request"]

NOT_SET = Sentinel("NOT_SET")


class ProvideMarker:
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

    def __class_getitem__(cls, interface: Any) -> Any:
        return Annotated[interface, cls()]


if TYPE_CHECKING:
    Provide = Annotated[T, ProvideMarker()]
else:
    Provide = ProvideMarker


def is_provide_marker(obj: Any) -> bool:
    return isinstance(obj, ProvideMarker)


def Inject() -> Any:
    return ProvideMarker()


class Event:
    """Represents an event object."""

    __slots__ = ()


def is_event_type(obj: Any) -> bool:
    """Checks if an object is an event type."""
    return inspect.isclass(obj) and issubclass(obj, Event)


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


def unwrap_parameter(parameter: inspect.Parameter) -> inspect.Parameter:
    if get_origin(parameter.annotation) is not Annotated:
        return parameter

    origin, *metadata = get_args(parameter.annotation)

    if not metadata or not is_provide_marker(metadata[-1]):
        return parameter

    if is_provide_marker(parameter.default):
        raise TypeError(
            "Cannot specify `Inject` in `Annotated` and "
            f"default value together for '{parameter.name}'"
        )

    if parameter.default is not inspect.Parameter.empty:
        return parameter

    marker = metadata[-1]
    new_metadata = metadata[:-1]
    if new_metadata:
        if hasattr(Annotated, "__getitem__"):
            new_annotation = Annotated.__getitem__((origin, *new_metadata))  # type: ignore
        else:
            new_annotation = Annotated.__class_getitem__((origin, *new_metadata))  # type: ignore
    else:
        new_annotation = origin
    return parameter.replace(annotation=new_annotation, default=marker)
