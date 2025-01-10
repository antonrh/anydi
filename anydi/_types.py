from __future__ import annotations

import inspect
from collections.abc import Iterable
from types import ModuleType
from typing import Annotated, Any, NamedTuple, Union

import wrapt
from typing_extensions import Literal, Self, TypeAlias

Scope = Literal["transient", "singleton", "request"]

AnyInterface: TypeAlias = Union[type[Any], Annotated[Any, ...]]


class Marker:
    """A marker class for marking dependencies."""

    __slots__ = ()

    def __call__(self) -> Self:
        return self


def is_marker(obj: Any) -> bool:
    """Checks if an object is a marker."""
    return isinstance(obj, Marker)


class Event:
    """Represents an event object."""

    __slots__ = ()


def is_event_type(obj: Any) -> bool:
    """Checks if an object is an event type."""
    return inspect.isclass(obj) and issubclass(obj, Event)


class InstanceProxy(wrapt.ObjectProxy):  # type: ignore[misc]
    def __init__(self, wrapped: Any, *, interface: type[Any]) -> None:
        super().__init__(wrapped)
        self._self_interface = interface

    @property
    def interface(self) -> type[Any]:
        return self._self_interface

    def __getattribute__(self, item: str) -> Any:
        if item in "interface":
            return object.__getattribute__(self, item)
        return object.__getattribute__(self, item)


class ProviderDecoratorArgs(NamedTuple):
    scope: Scope
    override: bool


class Dependency(NamedTuple):
    member: Any
    module: ModuleType


class InjectableDecoratorArgs(NamedTuple):
    wrapped: bool
    tags: Iterable[str] | None
