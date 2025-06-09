from __future__ import annotations

import inspect
from collections.abc import Iterable
from typing import Any, TypedDict

from typing_extensions import Self

from ._scope import Scope

NOT_SET = object()


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


class ProviderMetadata(TypedDict):
    scope: Scope
    override: bool


class InjectableMetadata(TypedDict):
    wrapped: bool
    tags: Iterable[str] | None
