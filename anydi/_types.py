"""Shared AnyDI utils module."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Iterator
from types import NoneType
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
    TypeVar,
)

from typing_extensions import Sentinel

T = TypeVar("T")

Scope = Literal["transient", "singleton", "request"]

NOT_SET = Sentinel("NOT_SET")


class ProvideMarker:
    """A marker object for declaring dependency."""

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

    def __class_getitem__(cls, item: Any) -> Any:
        return Annotated[item, cls()]


def is_provide_marker(obj: Any) -> bool:
    return isinstance(obj, ProvideMarker)


if TYPE_CHECKING:
    Provide = Annotated[T, ProvideMarker()]
else:
    Provide = ProvideMarker


def Inject() -> Any:
    return ProvideMarker()


# Alias from backward compatibility
is_inject_marker = is_provide_marker


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
