"""Shared AnyDI utils module."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Iterator
from types import NoneType
from typing import Any, ForwardRef, Literal

from typing_extensions import Sentinel, evaluate_forward_ref

Scope = Literal["transient", "singleton", "request"] | str

NOT_SET = Sentinel("NOT_SET")


class Event:
    """Represents an event object."""

    __slots__ = ()


def evaluate_annotation(annotation: Any, module: Any | None = None) -> Any:
    """Evaluate an annotation, falling back to ForwardRef on NameError."""
    if isinstance(annotation, str):
        forward_ref = ForwardRef(annotation, module=module)
        try:
            return evaluate_forward_ref(forward_ref)
        except NameError:
            # Name not defined yet - return ForwardRef for lazy resolution
            return forward_ref
    return annotation


def resolve_forward_ref(annotation: Any) -> Any:
    """Resolve a ForwardRef annotation to its actual type."""
    if isinstance(annotation, ForwardRef):
        return evaluate_forward_ref(annotation)
    return annotation


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
