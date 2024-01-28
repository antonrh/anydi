"""PyxDI decorators module."""
import typing as t

from typing_extensions import Concatenate, ParamSpec

from .core import Module, Scope

T = t.TypeVar("T", bound=t.Any)
M = t.TypeVar("M", bound=Module)
P = ParamSpec("P")


def provider(
    *, scope: Scope, override: bool = False
) -> t.Callable[[t.Callable[Concatenate[M, P], T]], t.Callable[Concatenate[M, P], T]]:
    """Decorator for marking a function or method as a provider in a PyxDI module.

    Args:
        scope: The scope in which the provided instance should be managed.
        override: Whether the provider should override existing providers
            with the same interface.

    Returns:
        A decorator that marks the target function or method as a provider.
    """

    def decorator(
        target: t.Callable[Concatenate[M, P], T],
    ) -> t.Callable[Concatenate[M, P], T]:
        setattr(
            target,
            "__pyxdi_provider__",
            {
                "scope": scope,
                "override": override,
            },
        )
        return target

    return decorator


@t.overload
def inject(obj: t.Callable[P, T]) -> t.Callable[P, T]:
    ...


@t.overload
def inject(
    *, tags: t.Optional[t.Iterable[str]] = None
) -> t.Callable[
    [t.Callable[P, t.Union[T, t.Awaitable[T]]]],
    t.Callable[P, t.Union[T, t.Awaitable[T]]],
]:
    ...


def inject(  # type: ignore[misc]
    obj: t.Union[t.Callable[P, t.Union[T, t.Awaitable[T]]], None] = None,
    tags: t.Optional[t.Iterable[str]] = None,
) -> t.Union[
    t.Callable[
        [t.Callable[P, t.Union[T, t.Awaitable[T]]]],
        t.Callable[P, t.Union[T, t.Awaitable[T]]],
    ],
    t.Callable[P, t.Union[T, t.Awaitable[T]]],
]:
    """Decorator for marking a function or method as requiring dependency injection.

    Args:
        obj: The target function or method to be decorated.
        tags: Optional tags to associate with the injection point.

    Returns:
        If `obj` is provided, returns the decorated target function or method.
        If `obj` is not provided, returns a decorator that can be used to mark
        a function or method as requiring dependency injection.
    """

    def decorator(
        obj: t.Callable[P, t.Union[T, t.Awaitable[T]]],
    ) -> t.Callable[P, t.Union[T, t.Awaitable[T]]]:
        setattr(obj, "__pyxdi_inject__", True)
        setattr(obj, "__pyxdi_tags__", tags)
        return obj

    if obj is None:
        return decorator

    return decorator(obj)


def transient(target: T) -> T:
    """Decorator for marking a class as transient scope.

    Args:
        target: The target class to be decorated.

    Returns:
        The decorated target class.
    """
    setattr(target, "__pyxdi_scope__", "transient")
    return target


def request(target: T) -> T:
    """Decorator for marking a class as request scope.

    Args:
        target: The target class to be decorated.

    Returns:
        The decorated target class.
    """
    setattr(target, "__pyxdi_scope__", "request")
    return target


def singleton(target: T) -> T:
    """Decorator for marking a class as singleton scope.

    Args:
        target: The target class to be decorated.

    Returns:
        The decorated target class.
    """
    setattr(target, "__pyxdi_scope__", "singleton")
    return target
