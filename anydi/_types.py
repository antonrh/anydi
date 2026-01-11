"""Shared AnyDI utils module."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Iterator
from types import NoneType
from typing import Any, ForwardRef, Generic, Literal, TypeVar, get_args, get_origin

from typing_extensions import Sentinel, evaluate_forward_ref

Scope = Literal["transient", "singleton", "request"] | str

NOT_SET = Sentinel("NOT_SET")

T = TypeVar("T")


class FromContext(Generic[T]):
    """Marker type for dependencies provided via context.set()."""

    __slots__ = ()


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


def is_from_context(annotation: Any) -> bool:
    """Check if annotation is FromContext[T]."""
    origin = get_origin(annotation)
    return origin is FromContext


def get_from_context_type(annotation: Any) -> Any:
    """Extract the inner type from FromContext[T]."""
    if not is_from_context(annotation):
        raise ValueError(f"Annotation {annotation} is not FromContext[T]")
    args = get_args(annotation)
    if not args:
        raise ValueError("FromContext requires a type argument: FromContext[T]")
    return args[0]
