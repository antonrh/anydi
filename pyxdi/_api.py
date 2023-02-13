import contextlib
import threading
import typing as t
from types import ModuleType

try:
    import anyio  # noqa

    anyio_installed = True
except ImportError:
    anyio_installed = False

from ._contstants import DEFAULT_MODE
from ._core import DI, Context, Dependency
from ._types import Mode, Provider, ProviderFunctionT, Scope
from ._utils import scan_package

if t.TYPE_CHECKING:
    from ._async import AsyncContext, AsyncDI


_di: t.Optional[DI] = None
_async_di: t.Optional["AsyncDI"] = None
_lock = threading.RLock()


dep = Dependency()


def _get_di() -> DI:
    global _di

    if _di is None:
        raise RuntimeError(
            '`pyxdi` not initialized. Please, call `pyxdi.init(mode="sync")` first.'
        )
    return _di


def _get_async_di() -> "AsyncDI":
    global _async_di

    if _async_di is None:
        raise RuntimeError(
            "`pyxdi` not initialized. " 'Please, call `pyxdi.init(mode="async")` first.'
        )
    return _async_di


def _get_di_or_async_di() -> t.Union[DI, "AsyncDI"]:
    global _di
    global _async_di

    if _di is None and _async_di is None:
        raise RuntimeError(
            "`pyxdi` not initialized. Please, call `pyxdi.init()` first."
        )
    return t.cast(t.Union[DI, "AsyncDI"], _di or _async_di)


def init(
    *,
    mode: t.Optional[Mode] = None,
    default_scope: t.Optional[Scope] = None,
    packages: t.Optional[t.Iterable[t.Union[ModuleType | str]]] = None,
    include: t.Optional[t.Iterable[str]] = None,
) -> None:
    global _di
    global _async_di

    if _di or _async_di:
        if _di:
            raise RuntimeError("`pyxdi` already initialized in `sync` mode.")
        elif _async_di:
            raise RuntimeError("`pyxdi` already initialized in `async` mode.")

    mode = mode or DEFAULT_MODE

    with _lock:
        if mode == "sync" and _di or mode == "async" and _async_di:
            return

        if mode == "async":
            if not anyio_installed:
                raise RuntimeError(
                    "Please, install `async` extension run in asynchronous mode. "
                    "eg. pip install pyxdi[async]"
                )

            from ._async import AsyncDI

            _async_di = AsyncDI(default_scope=default_scope)
        else:
            _di = DI(default_scope=default_scope)

        packages = packages or []
        for package in packages:
            scan_package(package, include=include)


def close() -> None:
    di = _get_di()
    return di.close()


async def aclose() -> None:
    di = _get_async_di()
    await di.close()


@contextlib.contextmanager
def request_context() -> t.Iterator[Context]:
    di = _get_di()
    with di.request_context() as ctx:
        yield ctx


@contextlib.asynccontextmanager
async def arequest_context() -> t.AsyncIterator["AsyncContext"]:
    di = _get_async_di()
    async with di.request_context() as ctx:
        yield ctx


@t.overload
def provider(
    func: None = ...,
    *,
    scope: Scope | None = None,
    override: bool = False,
) -> t.Callable[..., t.Any]:
    ...


@t.overload
def provider(
    func: ProviderFunctionT,
    *,
    scope: Scope | None = None,
    override: bool = False,
) -> t.Callable[[Provider], t.Any]:
    ...


def provider(
    func: t.Union[ProviderFunctionT, None] = None,
    *,
    scope: Scope | None = None,
    override: bool = False,
) -> t.Union[ProviderFunctionT, t.Callable[[Provider], t.Any]]:
    di = _get_di_or_async_di()
    provide = di.provide(scope=scope, override=override)

    if func is None:
        return provide
    elif callable(func):
        return provide(func)  # type: ignore[no-any-return]
    else:
        raise ValueError("Invalid provided dependency arguments.")


def inject(obj: t.Callable[..., t.Any]) -> t.Any:
    di = _get_di_or_async_di()
    return di.inject_callable(obj)
