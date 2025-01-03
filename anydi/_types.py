from __future__ import annotations

import inspect
from collections.abc import Iterable
from dataclasses import dataclass
from types import ModuleType
from typing import Annotated, Any, NamedTuple, Union

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


@dataclass(frozen=True)
class DependencyWrapper:
    interface: type[Any]
    instance: Any

    def __getattribute__(self, name: str) -> Any:
        if name in {"interface", "instance"}:
            return object.__getattribute__(self, name)
        return getattr(self.instance, name)


class ProviderDecoratorArgs(NamedTuple):
    scope: Scope
    override: bool


@dataclass(frozen=True)
class Dependency:
    member: Any
    module: ModuleType


class InjectableDecoratorArgs(NamedTuple):
    wrapped: bool
    tags: Iterable[str] | None
