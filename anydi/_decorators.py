from collections.abc import Iterable
from typing import Any, Callable, Concatenate, ParamSpec, TypedDict, TypeVar, overload

from ._module import Module
from ._scope import Scope

T = TypeVar("T", bound=Any)
P = ParamSpec("P")
M = TypeVar("M", bound=Module)


def transient(cls: T) -> T:
    """Decorator for marking a class as transient scope."""
    cls.__scope__ = "transient"
    return cls


def request(cls: T) -> T:
    """Decorator for marking a class as request scope."""
    cls.__scope__ = "request"
    return cls


def singleton(cls: T) -> T:
    """Decorator for marking a class as singleton scope."""
    cls.__scope__ = "singleton"
    return cls


class ProviderMetadata(TypedDict):
    scope: Scope
    override: bool


def provider(
    *, scope: Scope, override: bool = False
) -> Callable[[Callable[Concatenate[M, P], T]], Callable[Concatenate[M, P], T]]:
    """Decorator for marking a function or method as a provider in a AnyDI module."""

    def decorator(
        target: Callable[Concatenate[M, P], T],
    ) -> Callable[Concatenate[M, P], T]:
        target.__provider__ = ProviderMetadata(scope=scope, override=override)  # type: ignore
        return target

    return decorator


class InjectableMetadata(TypedDict):
    wrapped: bool
    tags: Iterable[str] | None


@overload
def injectable(func: Callable[P, T]) -> Callable[P, T]: ...


@overload
def injectable(
    *, tags: Iterable[str] | None = None
) -> Callable[[Callable[P, T]], Callable[P, T]]: ...


def injectable(
    func: Callable[P, T] | None = None,
    tags: Iterable[str] | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]] | Callable[P, T]:
    """Decorator for marking a function or method as requiring dependency injection."""

    def decorator(inner: Callable[P, T]) -> Callable[P, T]:
        inner.__injectable__ = InjectableMetadata(wrapped=True, tags=tags)  # type: ignore
        return inner

    if func is None:
        return decorator

    return decorator(func)
