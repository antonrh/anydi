from __future__ import annotations

import enum
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ._types import NOT_SET, Scope


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


@dataclass(frozen=True, slots=True)
class ProviderParameter:
    name: str
    annotation: Any
    default: Any
    has_default: bool
    provider: Provider | None = None
    shared_scope: bool = False


@dataclass(frozen=True, slots=True)
class Provider:
    call: Callable[..., Any]
    scope: Scope
    interface: Any
    name: str
    parameters: tuple[ProviderParameter, ...]
    is_class: bool
    is_coroutine: bool
    is_generator: bool
    is_async_generator: bool
    is_async: bool
    is_resource: bool


@dataclass(frozen=True, slots=True)
class ProviderDef:
    call: Callable[..., Any]
    scope: Scope
    interface: Any = NOT_SET
