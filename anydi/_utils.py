"""Shared AnyDI utils module."""

import builtins
import functools
import inspect
import sys
from typing import Any, Callable, Dict, Type, TypeVar

from typing_extensions import Annotated, ParamSpec, get_origin

try:
    import anyio  # noqa
except ImportError:
    anyio = None  # type: ignore[assignment]


T = TypeVar("T")
P = ParamSpec("P")


def get_full_qualname(obj: Any) -> str:
    """Get the fully qualified name of an object.

    This function returns the fully qualified name of the given object,
    which includes both the module name and the object's qualname.

    Args:
        obj: The object for which to retrieve the fully qualified name.

    Returns:
        The fully qualified name of the object.
    """
    origin = get_origin(obj)
    if origin is Annotated:
        metadata = ", ".join(
            [
                f'"{arg}"' if isinstance(arg, str) else str(arg)
                for arg in obj.__metadata__
            ]
        )
        return f"Annotated[{get_full_qualname(obj.__args__[0])}, {metadata}]]"

    qualname = getattr(obj, "__qualname__", None)
    module_name = getattr(obj, "__module__", None)
    if qualname is None:
        qualname = type(obj).__qualname__

    if module_name is None:
        module_name = type(obj).__module__

    if module_name == builtins.__name__:
        return qualname
    return f"{module_name}.{qualname}"


def is_builtin_type(tp: Type[Any]) -> bool:
    """
    Check if the given type is a built-in type.
    Args:
        tp (type): The type to check.
    Returns:
        bool: True if the type is a built-in type, False otherwise.
    """
    return tp.__module__ == builtins.__name__


@functools.lru_cache(maxsize=None)
def get_signature(obj: Callable[..., Any]) -> inspect.Signature:
    """Get the signature of a callable object.

    This function uses the `inspect.signature` function to retrieve the signature
    of the given callable object. It applies an LRU cache decorator to improve
    performance by caching the signatures of previously inspected objects.

    Args:
        obj: The callable object to inspect.

    Returns:
        The signature of the callable object.
    """
    signature_kwargs: Dict[str, Any] = {}
    if sys.version_info >= (3, 10):
        signature_kwargs["eval_str"] = True
    return inspect.signature(obj, **signature_kwargs)


async def run_async(
    func: Callable[P, T],
    /,
    *args: P.args,
    **kwargs: P.kwargs,
) -> T:
    """Runs the given function asynchronously using the `anyio` library.

    Args:
        func: The function to run asynchronously.
        args: The positional arguments to pass to the function.
        kwargs: The keyword arguments to pass to the function.

    Returns:
        The result of the function.

    Raises:
        ImportError: If the `anyio` library is not installed.
    """
    if not anyio:
        raise ImportError(
            "`anyio` library is not currently installed. Please make sure to install "
            "it first, or consider using `anydi[full]` instead."
        )
    return await anyio.to_thread.run_sync(functools.partial(func, *args, **kwargs))
