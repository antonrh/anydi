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

from typing_extensions import NotRequired

if TYPE_CHECKING:
    from ._module import Module


from ._types import NOT_SET, Scope

T = TypeVar("T")
P = ParamSpec("P")

ClassT = TypeVar("ClassT", bound=type)
ModuleT = TypeVar("ModuleT", bound="Module")


class ProvidedMetadata(TypedDict):
    """Metadata for classes marked as provided by AnyDI."""

    dependency_type: NotRequired[Any]
    scope: Scope
    from_context: bool


@overload
def provided(
    dependency_type: Any, /, *, scope: Scope, from_context: bool = False
) -> Callable[[ClassT], ClassT]: ...


@overload
def provided(
    *, scope: Scope, from_context: bool = False
) -> Callable[[ClassT], ClassT]: ...


def provided(
    dependency_type: Any = NOT_SET, /, *, scope: Scope, from_context: bool = False
) -> Callable[[ClassT], ClassT]:
    """Decorator for marking a class as provided by AnyDI with a specific scope."""

    def decorator(cls: ClassT) -> ClassT:
        metadata: ProvidedMetadata = {"scope": scope, "from_context": from_context}
        if dependency_type is not NOT_SET:
            metadata["dependency_type"] = dependency_type
        cls.__provided__ = metadata  # type: ignore[attr-defined]
        return cls

    return decorator


@overload
def singleton(cls: ClassT, /) -> ClassT: ...


@overload
def singleton(
    cls: None = None, /, *, dependency_type: Any = NOT_SET
) -> Callable[[ClassT], ClassT]: ...


def singleton(
    cls: ClassT | None = None, /, *, dependency_type: Any = NOT_SET
) -> Callable[[ClassT], ClassT] | ClassT:
    """Decorator for marking a class as a singleton dependency."""

    def decorator(c: ClassT) -> ClassT:
        metadata: ProvidedMetadata = {"scope": "singleton", "from_context": False}
        if dependency_type is not NOT_SET:
            metadata["dependency_type"] = dependency_type
        c.__provided__ = metadata  # type: ignore[attr-defined]
        return c

    if cls is None:
        return decorator

    return decorator(cls)


@overload
def transient(cls: ClassT, /) -> ClassT: ...


@overload
def transient(
    cls: None = None, /, *, dependency_type: Any = NOT_SET
) -> Callable[[ClassT], ClassT]: ...


def transient(
    cls: ClassT | None = None, /, *, dependency_type: Any = NOT_SET
) -> Callable[[ClassT], ClassT] | ClassT:
    """Decorator for marking a class as a transient dependency."""

    def decorator(c: ClassT) -> ClassT:
        metadata: ProvidedMetadata = {"scope": "transient", "from_context": False}
        if dependency_type is not NOT_SET:
            metadata["dependency_type"] = dependency_type
        c.__provided__ = metadata  # type: ignore[attr-defined]
        return c

    if cls is None:
        return decorator

    return decorator(cls)


@overload
def request(cls: ClassT, /, *, from_context: bool = False) -> ClassT: ...


@overload
def request(
    cls: None = None, /, *, dependency_type: Any = NOT_SET, from_context: bool = False
) -> Callable[[ClassT], ClassT]: ...


def request(
    cls: ClassT | None = None,
    /,
    *,
    dependency_type: Any = NOT_SET,
    from_context: bool = False,
) -> Callable[[ClassT], ClassT] | ClassT:
    """Decorator for marking a class as a request-scoped dependency."""

    def decorator(c: ClassT) -> ClassT:
        metadata: ProvidedMetadata = {"scope": "request", "from_context": from_context}
        if dependency_type is not NOT_SET:
            metadata["dependency_type"] = dependency_type
        c.__provided__ = metadata  # type: ignore[attr-defined]
        return c

    if cls is None:
        return decorator

    return decorator(cls)


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
