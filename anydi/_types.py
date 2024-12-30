from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Annotated, Any, TypeVar, Union

from typing_extensions import Literal, Self, TypeAlias

Scope = Literal["transient", "singleton", "request"]

T = TypeVar("T")
AnyInterface: TypeAlias = Union[type[Any], Annotated[Any, ...]]
Interface: TypeAlias = type[T]


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
class TestInterface:
    interface: type[Any]
