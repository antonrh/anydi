import typing as t

from typing_extensions import Concatenate, ParamSpec

from .core import Module, Scope

T = t.TypeVar("T", bound=t.Any)
M = t.TypeVar("M", bound=Module)
P = ParamSpec("P")


def provider(
    *, scope: Scope, override: bool = False
) -> t.Callable[[t.Callable[Concatenate[M, P], T]], t.Callable[Concatenate[M, P], T]]:
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

    return decorator


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
