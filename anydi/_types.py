from __future__ import annotations

import enum
import inspect
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cached_property
from types import ModuleType
from typing import Annotated, Any, Callable, NamedTuple, Union

import wrapt
from typing_extensions import Literal, Self, TypeAlias

Scope = Literal["transient", "singleton", "request"]

AnyInterface: TypeAlias = Union[type[Any], Annotated[Any, ...]]

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


class ProviderKind(enum.IntEnum):
    CLASS = 1
    FUNCTION = 2
    COROUTINE = 3
    GENERATOR = 4
    ASYNC_GENERATOR = 5

    @classmethod
    def from_call(cls, call: Callable[..., Any]) -> ProviderKind:
        if inspect.isclass(call):
            return cls.CLASS
        elif inspect.iscoroutinefunction(call):
            return cls.COROUTINE
        elif inspect.isasyncgenfunction(call):
            return cls.ASYNC_GENERATOR
        elif inspect.isgeneratorfunction(call):
            return cls.GENERATOR
        elif inspect.isfunction(call) or inspect.ismethod(call):
            return cls.FUNCTION
        raise TypeError(
            f"The provider `{call}` is invalid because it is not a callable "
            "object. Only callable providers are allowed."
        )


@dataclass(kw_only=True, frozen=True)
class ProviderParameter:
    pass


@dataclass(kw_only=True, frozen=True)
class Provider:
    call: Callable[..., Any]
    scope: Scope
    interface: Any
    name: str
    parameters: list[inspect.Parameter]
    kind: ProviderKind

    def __str__(self) -> str:
        return self.name

    @cached_property
    def is_class(self) -> bool:
        return self.kind == ProviderKind.CLASS

    @cached_property
    def is_coroutine(self) -> bool:
        return self.kind == ProviderKind.COROUTINE

    @cached_property
    def is_generator(self) -> bool:
        return self.kind == ProviderKind.GENERATOR

    @cached_property
    def is_async_generator(self) -> bool:
        return self.kind == ProviderKind.ASYNC_GENERATOR

    @cached_property
    def is_async(self) -> bool:
        return self.is_coroutine or self.is_async_generator

    @cached_property
    def is_resource(self) -> bool:
        return self.is_generator or self.is_async_generator


class ProviderArgs(NamedTuple):
    call: Callable[..., Any]
    scope: Scope
    interface: Any = NOT_SET


class ProviderDecoratorArgs(NamedTuple):
    scope: Scope
    override: bool


class ScannedDependency(NamedTuple):
    member: Any
    module: ModuleType


class InjectableDecoratorArgs(NamedTuple):
    wrapped: bool
    tags: Iterable[str] | None
