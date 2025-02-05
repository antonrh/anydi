from __future__ import annotations

import inspect
from dataclasses import dataclass
from enum import IntEnum
from functools import cached_property
from typing import Any, Callable

from ._types import Scope


class ProviderKind(IntEnum):
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
