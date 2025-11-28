"""Shared AnyDI utils module."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Callable, Iterator
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


_provide_factory: Callable[[], Any] = ProvideMarker


def set_provide_factory(factory: Callable[[], Any]) -> Callable[[], Any]:
    """Set the global factory used by Inject() and Provide."""
    global _provide_factory
    previous = _provide_factory
    _provide_factory = factory
    return previous


def is_provide_marker(obj: Any) -> bool:
    return isinstance(obj, ProvideMarker)


class _ProvideMeta(type):
    """Metaclass for Provide that delegates __class_getitem__ to the current factory."""

    def __getitem__(cls, item: Any) -> Any:
        # Use the current factory's __class_getitem__ if available
        factory = _provide_factory
        if hasattr(factory, "__class_getitem__"):
            return factory.__class_getitem__(item)  # type: ignore[attr-defined]
        # Fallback to creating Annotated with factory instance
        return Annotated[item, factory()]


if TYPE_CHECKING:
    Provide = Annotated[T, ProvideMarker()]

else:

    class Provide(metaclass=_ProvideMeta):
        pass


def Inject() -> Any:
    return _provide_factory()


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
