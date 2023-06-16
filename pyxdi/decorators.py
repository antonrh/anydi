import typing as t

from typing_extensions import Concatenate, ParamSpec

from .core import Module, Scope

T = t.TypeVar("T", bound=t.Any)
M = t.TypeVar("M", bound=Module)
P = ParamSpec("P")


@t.overload
def provider(
    target: t.Callable[Concatenate[M, P], T]
) -> t.Callable[Concatenate[M, P], T]:
    ...


@t.overload
def provider(
    *,
    scope: t.Optional[Scope] = None,
    override: t.Optional[bool] = None,
) -> t.Callable[[t.Callable[Concatenate[M, P], T]], t.Callable[Concatenate[M, P], T]]:
    ...


def provider(
    target: t.Optional[t.Callable[Concatenate[M, P], T]] = None,
    *,
    scope: t.Optional[Scope] = None,
    override: t.Optional[bool] = None,
) -> t.Union[
    t.Callable[Concatenate[M, P], T],
    t.Callable[[t.Callable[Concatenate[M, P], T]], t.Callable[Concatenate[M, P], T]],
]:
    def decorator(
        target: t.Callable[Concatenate[M, P], T]
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
    *, tags: t.Optional[t.Iterable[str]] = None
) -> t.Callable[
    [t.Callable[P, t.Union[T, t.Awaitable[T]]]],
    t.Callable[P, t.Union[T, t.Awaitable[T]]],
]:
    ...


def inject(
    obj: t.Union[t.Callable[P, t.Union[T, t.Awaitable[T]]], None] = None,
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
        setattr(obj, "__pyxdi_inject__", True)
        setattr(obj, "__pyxdi_tags__", tags)
        return obj

    if obj is None:
        return decorator

    return decorator(obj)
