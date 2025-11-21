from collections.abc import Callable, Iterable
from typing import (
    TYPE_CHECKING,
    Any,
    Concatenate,
    ParamSpec,
    Protocol,
    TypedDict,
    TypeGuard,
    TypeVar,
    overload,
)

if TYPE_CHECKING:
    from ._module import Module


from ._types import Scope

T = TypeVar("T")
P = ParamSpec("P")

ClassT = TypeVar("ClassT", bound=type)
ModuleT = TypeVar("ModuleT", bound="Module")


class ProvidedMetadata(TypedDict):
    """Metadata for classes marked as provided by AnyDI."""

    scope: Scope


def provided(*, scope: Scope) -> Callable[[ClassT], ClassT]:
    """Decorator for marking a class as provided by AnyDI with a specific scope."""

    def decorator(cls: ClassT) -> ClassT:
        cls.__provided__ = ProvidedMetadata(scope=scope)
        return cls

    return decorator


# Scoped decorators for class-level providers
transient = provided(scope="transient")
request = provided(scope="request")
singleton = provided(scope="singleton")


class Provided(Protocol):
    __provided__: ProvidedMetadata


def is_provided(cls: Any) -> TypeGuard[type[Provided]]:
    return hasattr(cls, "__provided__")


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


class Provider(Protocol):
    __provider__: ProviderMetadata


def is_provider(obj: Callable[..., Any]) -> TypeGuard[Provider]:
    return hasattr(obj, "__provider__")


class InjectableMetadata(TypedDict):
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
        inner.__injectable__ = InjectableMetadata(tags=tags)  # type: ignore
        return inner

    if func is None:
        return decorator

    return decorator(func)


class Injectable(Protocol):
    __injectable__: InjectableMetadata


def is_injectable(obj: Callable[..., Any]) -> TypeGuard[Injectable]:
    return hasattr(obj, "__injectable__")
