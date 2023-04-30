import typing as t

from typing_extensions import ParamSpec

from .types import Scope

T = t.TypeVar("T", bound=t.Any)
P = ParamSpec("P")


def transient(target: T) -> T:
    setattr(target, "__pyxdi_scope__", "transient")
    return target


def request(target: T) -> T:
    setattr(target, "__pyxdi_scope__", "request")
    return target


def singleton(target: T) -> T:
    setattr(target, "__pyxdi_scope__", "singleton")
    return target


@t.overload
def provider(target: t.Callable[P, T]) -> t.Callable[P, T]:
    ...


@t.overload
def provider(
    *,
    scope: t.Optional[Scope] = None,
    tags: t.Optional[t.Iterable[str]] = None,
) -> t.Callable[[t.Callable[P, T]], t.Callable[P, T]]:
    ...


def provider(
    target: t.Optional[t.Callable[P, T]] = None,
    *,
    scope: t.Optional[Scope] = None,
    tags: t.Optional[t.Iterable[str]] = None,
) -> t.Union[t.Callable[P, T], t.Callable[[t.Callable[P, T]], t.Callable[P, T]]]:
    def decorator(target: t.Callable[P, T]) -> t.Callable[P, T]:
        setattr(
            target,
            "__pyxdi_provider__",
            {
                "scope": scope,
            },
        )
        setattr(target, "__pyxdi_tags__", tags)
        return target

    if target is None:
        return decorator
    return decorator(target)


@t.overload
def inject(obj: t.Callable[P, T]) -> t.Callable[P, T]:
    ...


@t.overload
def inject(obj: t.Callable[P, t.Awaitable[T]]) -> t.Callable[P, t.Awaitable[T]]:
    ...


@t.overload
def inject(
    *, lazy: t.Optional[bool] = None, tags: t.Optional[t.Iterable[str]] = None
) -> t.Callable[
    [t.Callable[P, t.Union[T, t.Awaitable[T]]]],
    t.Callable[P, t.Union[T, t.Awaitable[T]]],
]:
    ...


def inject(
    obj: t.Union[t.Callable[P, t.Union[T, t.Awaitable[T]]], None] = None,
    lazy: t.Optional[bool] = None,
    tags: t.Optional[t.Iterable[str]] = None,
) -> t.Union[
    t.Callable[
        [t.Callable[P, t.Union[T, t.Awaitable[T]]]],
        t.Callable[P, t.Union[T, t.Awaitable[T]]],
    ],
    t.Callable[P, t.Union[T, t.Awaitable[T]]],
]:
    def decorator(
        obj: t.Callable[P, t.Union[T, t.Awaitable[T]]]
    ) -> t.Callable[P, t.Union[T, t.Awaitable[T]]]:
        setattr(
            obj,
            "__pyxdi_inject__",
            {
                "lazy": lazy,
            },
        )
        setattr(obj, "__pyxdi_tags__", tags)
        return obj

    if obj is None:
        return decorator

    return decorator(obj)
