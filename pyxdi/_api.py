import contextlib
import threading
import typing as t
from types import ModuleType

try:
    import anyio  # noqa

    anyio_installed = True
except ImportError:  # pragma: no cover
    anyio_installed = False

from ._contstants import DEFAULT_MODE
from ._core import DependencyParam, DIContext, ScopedContext
from ._types import Mode, Provider, ProviderFunctionT, Scope
from ._utils import scan_package

if t.TYPE_CHECKING:
    from ._async import AsyncDIContext, AsyncScopedContext


_di_context: t.Optional[DIContext] = None
_async_di_context: t.Optional["AsyncDIContext"] = None
_lock = threading.RLock()


dep = DependencyParam()


def _get_di_context() -> DIContext:
    global _di_context

    if _di_context is None:
        raise RuntimeError(
            '`pyxdi` not initialized. Please, call `pyxdi.init(mode="sync")` first.'
        )
    return _di_context


def _get_async_di_context() -> "AsyncDIContext":
    global _async_di_context

    if _async_di_context is None:
        raise RuntimeError(
            "`pyxdi` not initialized. " 'Please, call `pyxdi.init(mode="async")` first.'
        )
    return _async_di_context


def _get_di_or_async_di_context() -> t.Union[DIContext, "AsyncDIContext"]:
    global _di_context
    global _async_di_context

    if _di_context is None and _async_di_context is None:
        raise RuntimeError(
            "`pyxdi` not initialized. Please, call `pyxdi.init()` first."
        )
    return t.cast(
        t.Union[DIContext, "AsyncDIContext"],
        _di_context or _async_di_context,
    )


def init(
    *,
    mode: t.Optional[Mode] = None,
    autobind: t.Optional[bool] = None,
    default_scope: t.Optional[Scope] = None,
    packages: t.Optional[t.Iterable[t.Union[ModuleType | str]]] = None,
    include: t.Optional[t.Iterable[str]] = None,
) -> None:
    global _di_context
    global _async_di_context

    if _di_context or _async_di_context:
        if _di_context:
            raise RuntimeError("`pyxdi` already initialized in `sync` mode.")
        elif _async_di_context:
            raise RuntimeError("`pyxdi` already initialized in `async` mode.")

    mode = mode or DEFAULT_MODE

    with _lock:
        if (
            mode == "sync" and _di_context or mode == "async" and _async_di_context
        ):  # pragma: no cover
            return

        if mode == "async":
            if not anyio_installed:
                raise RuntimeError(
                    "Please, install `async` extension run in asynchronous mode. "
                    "eg. pip install pyxdi[async]."
                )

            from ._async import AsyncDIContext

            _async_di_context = AsyncDIContext(
                default_scope=default_scope, autobind=autobind
            )
        else:
            _di_context = DIContext(default_scope=default_scope, autobind=autobind)

        packages = packages or []
        for package in packages:
            scan_package(package, include=include)


def close() -> None:
    global _di_context
    if _di_context:
        _di_context.close()
        _di_context = None


async def aclose() -> None:
    global _async_di_context
    if _async_di_context:
        await _async_di_context.close()
        _async_di_context = None


@contextlib.contextmanager
def request_context() -> t.Iterator[ScopedContext]:
    di = _get_di_context()
    with di.request_context() as ctx:
        yield ctx


@contextlib.asynccontextmanager
async def arequest_context() -> t.AsyncIterator["AsyncScopedContext"]:
    di = _get_async_di_context()
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
    di_context = _get_di_or_async_di_context()
    provide = di_context.provide(scope=scope, override=override)
    if func is None:
        return provide
    return provide(func)  # type: ignore[no-any-return]


def inject(obj: t.Callable[..., t.Any]) -> t.Any:
    di_context = _get_di_or_async_di_context()
    return di_context.inject_callable(obj)
