"""Shared AnyDI utils module."""

from __future__ import annotations

import builtins
import functools
import importlib
from typing import Any, AsyncIterator, Callable, Iterator, TypeVar

from typing_extensions import ParamSpec, get_args, get_origin

try:
    import anyio  # noqa
except ImportError:
    anyio = None  # type: ignore[assignment]


T = TypeVar("T")
P = ParamSpec("P")


def get_full_qualname(obj: Any) -> str:
    """Get the fully qualified name of an object."""
    qualname = getattr(obj, "__qualname__", None)
    module = getattr(obj, "__module__", None)

    if qualname is None:
        qualname = type(obj).__qualname__

    if module is None:
        module = type(obj).__module__

    if module == builtins.__name__:
        return qualname

    origin = get_origin(obj)

    if origin:
        args = ", ".join(
            get_full_qualname(arg) if not isinstance(arg, str) else f'"{arg}"'
            for arg in get_args(obj)
        )
        return f"{get_full_qualname(origin)}[{args}]"

    return f"{module}.{qualname}"


def is_builtin_type(tp: type[Any]) -> bool:
    """Check if the given type is a built-in type."""
    return tp.__module__ == builtins.__name__


_resource_origins = (
    get_origin(Iterator),
    get_origin(AsyncIterator),
)


def has_resource_origin(origin: Any) -> bool:
    """Check if the given origin is a resource origin."""
    return origin in _resource_origins


async def run_async(
    func: Callable[P, T],
    /,
    *args: P.args,
    **kwargs: P.kwargs,
) -> T:
    """Runs the given function asynchronously using the `anyio` library."""
    if not anyio:
        raise ImportError(
            "`anyio` library is not currently installed. Please make sure to install "
            "it first, or consider using `anydi[full]` instead."
        )
    return await anyio.to_thread.run_sync(functools.partial(func, *args, **kwargs))


def import_string(dotted_path: str) -> Any:
    """
    Import a module or a specific attribute from a module using its dotted string path.

    Args:
        dotted_path: The dotted path to the object to import.

    Returns:
        object: The imported module or attribute/class/function.

    Raises:
        ImportError: If the import fails.
    """
    try:
        module_path, _, attribute_name = dotted_path.rpartition(".")
        if module_path:
            module = importlib.import_module(module_path)
            return getattr(module, attribute_name)
        else:
            return importlib.import_module(attribute_name)
    except (ImportError, AttributeError) as exc:
        raise ImportError(f"Cannot import '{dotted_path}': {exc}") from exc
