import typing as t

from .types import Scope

T = t.TypeVar("T")


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
def provider(target: T) -> T:
    ...


@t.overload
def provider(
    *,
    scope: t.Optional[Scope] = None,
    tags: t.Optional[t.Iterable[str]] = None,
) -> t.Callable[[T], T]:
    ...


def provider(
    target: t.Optional[T] = None,
    *,
    scope: t.Optional[Scope] = None,
    tags: t.Optional[t.Iterable[str]] = None,
) -> t.Union[T, t.Callable[[T], T]]:
    def decorator(target: T) -> T:
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
def inject(target: T) -> T:
    ...


@t.overload
def inject(*, tags: t.Optional[t.Iterable[str]] = None) -> t.Callable[[T], T]:
    ...


def inject(
    target: t.Optional[T] = None, *, tags: t.Optional[t.Iterable[str]] = None
) -> t.Union[T, t.Callable[[T], T]]:
    def decorator(target: T) -> T:
        setattr(target, "__pyxdi_inject__", True)
        setattr(target, "__pyxdi_tags__", tags)
        return target

    if target is None:
        return decorator

    return decorator(target)
