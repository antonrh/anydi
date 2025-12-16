"""Shared AnyDI utils module."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Iterator
from types import NoneType
from typing import TYPE_CHECKING, Annotated, Any, Literal, TypeVar

from typing_extensions import Sentinel

T = TypeVar("T")

Scope = Literal["transient", "singleton", "request"] | str

NOT_SET = Sentinel("NOT_SET")


class ProvideMarker:
    """A marker object for declaring dependency."""

    __slots__ = ("_interface", "_attrs", "_preferred_owner", "_current_owner")

    _FRAMEWORK_ATTRS = frozenset({"dependency", "use_cache", "cast", "cast_result"})

    def __init__(self, interface: Any = NOT_SET) -> None:
        # Avoid reinitializing attributes when mixins call __init__ multiple times
        if not hasattr(self, "_attrs"):
            super().__init__()
            self._attrs: dict[str, dict[str, Any]] = {}
            self._preferred_owner = "fastapi"
            self._current_owner: str | None = None
        self._interface = interface

    def set_owner(self, owner: str) -> None:
        self._preferred_owner = owner

    def _store_attr(self, name: str, value: Any) -> None:
        owner = self._current_owner or self._preferred_owner
        self._attrs.setdefault(owner, {})[name] = value

    def _get_attr(self, name: str) -> Any:
        owner = self._preferred_owner
        if owner in self._attrs and name in self._attrs[owner]:
            return self._attrs[owner][name]
        for attrs in self._attrs.values():
            if name in attrs:
                return attrs[name]
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self._FRAMEWORK_ATTRS and hasattr(self, "_attrs"):
            self._store_attr(name, value)
        else:
            super().__setattr__(name, value)

    def __getattr__(self, name: str) -> Any:
        if name in self._FRAMEWORK_ATTRS and hasattr(self, "_attrs"):
            return self._get_attr(name)
        raise AttributeError(name)

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


_provider_marker: type[ProvideMarker] = ProvideMarker


def register_provide_marker(provider_marker: type[ProvideMarker]) -> None:
    """Register an additional framework-specific provide marker."""

    global _provider_marker
    previous = _provider_marker

    if previous is ProvideMarker:
        _provider_marker = provider_marker
    else:
        name = f"ProvideMarker_{provider_marker.__name__}_{previous.__name__}"

        def __init__(self: ProvideMarker) -> None:
            provider_marker.__init__(self)
            previous.__init__(self)

        combined: type[ProvideMarker] = type(
            name, (provider_marker, previous), {"__init__": __init__}
        )
        _provider_marker = combined


def is_provide_marker(obj: Any) -> bool:
    return isinstance(obj, ProvideMarker)


class _ProvideMeta(type):
    """Metaclass for Provide that delegates __class_getitem__ to the current factory."""

    def __getitem__(cls, item: Any) -> Any:
        # Use the current _provider_marker_type's __class_getitem__ if available
        if hasattr(_provider_marker, "__class_getitem__"):
            return _provider_marker.__class_getitem__(item)  # type: ignore
        # Fallback to creating Annotated with factory instance
        return Annotated[item, _provider_marker.__class_getitem__(item)]


if TYPE_CHECKING:
    Provide = Annotated[T, ProvideMarker()]

else:

    class Provide(metaclass=_ProvideMeta):
        pass


def Inject() -> Any:
    return _provider_marker()


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
