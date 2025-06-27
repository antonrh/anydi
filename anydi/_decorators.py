from collections.abc import Iterable
from typing import Callable, Concatenate, ParamSpec, TypedDict, TypeVar, overload

from ._module import Module
from ._scope import Scope

T = TypeVar("T")
P = ParamSpec("P")

ClassT = TypeVar("ClassT", bound=type)
ModuleT = TypeVar("ModuleT", bound=Module)


def provided(*, scope: Scope) -> Callable[[ClassT], ClassT]:
    """Decorator for marking a class as provided by AnyDI with a specific scope."""

    def decorator(cls: ClassT) -> ClassT:
        cls.__provided__ = True
        cls.__scope__ = scope
        return cls

    return decorator


# Scoped decorators for class-level providers
transient = provided(scope="transient")
request = provided(scope="request")
singleton = provided(scope="singleton")


class ProviderMetadata(TypedDict):
    scope: Scope
    override: bool


def provider(
    *, scope: Scope, override: bool = False
) -> Callable[
    [Callable[Concatenate[ModuleT, P], T]], Callable[Concatenate[ModuleT, P], T]
]:
    """Decorator for marking a function or method as a provider in a AnyDI module."""

    def decorator(
        target: Callable[Concatenate[ModuleT, P], T],
    ) -> Callable[Concatenate[ModuleT, P], T]:
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
