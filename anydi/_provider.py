from __future__ import annotations

import enum
import inspect
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Callable, NamedTuple

from ._scope import Scope
from ._typing import NOT_SET


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
        if inspect.iscoroutinefunction(call):
            return cls.COROUTINE
        if inspect.isasyncgenfunction(call):
            return cls.ASYNC_GENERATOR
        if inspect.isgeneratorfunction(call):
            return cls.GENERATOR
        if inspect.isfunction(call) or inspect.ismethod(call):
            return cls.FUNCTION
        raise TypeError(
            f"The provider `{call}` is invalid because it is not a callable object."
        )

    @classmethod
    def is_resource(cls, kind: ProviderKind) -> bool:
        return kind in (cls.GENERATOR, cls.ASYNC_GENERATOR)


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
        return ProviderKind.is_resource(self.kind)


class ProviderDef(NamedTuple):
    call: Callable[..., Any]
    scope: Scope
    interface: Any = NOT_SET
