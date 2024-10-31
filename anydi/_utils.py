"""Shared AnyDI utils module."""

from __future__ import annotations

import builtins
import functools
import importlib
import inspect
import re
import sys
from typing import Any, Callable, ForwardRef, TypeVar

from typing_extensions import ParamSpec, get_args, get_origin

try:
    import anyio  # noqa
except ImportError:
    anyio = None  # type: ignore[assignment]


T = TypeVar("T")
P = ParamSpec("P")


def get_full_qualname(obj: Any) -> str:
    """Get the fully qualified name of an object."""
    # Get module and qualname with defaults to handle non-types directly
    module = getattr(obj, "__module__", type(obj).__module__)
    qualname = getattr(obj, "__qualname__", type(obj).__qualname__)

    origin = get_origin(obj)
    # If origin exists, handle generics recursively
    if origin:
        args = ", ".join(get_full_qualname(arg) for arg in get_args(obj))
        return f"{get_full_qualname(origin)}[{args}]"

    # Substitute standard library prefixes for clarity
    full_qualname = f"{module}.{qualname}"
    return re.sub(
        r"\b(builtins|typing|typing_extensions|collections\.abc|types)\.",
        "",
        full_qualname,
    )


def is_builtin_type(tp: type[Any]) -> bool:
    """Check if the given type is a built-in type."""
    return tp.__module__ == builtins.__name__


def get_typed_annotation(
    annotation: Any, globalns: dict[str, Any], module: Any = None
) -> Any:
    """Get the typed annotation of a callable object."""
    if isinstance(annotation, str):
        if sys.version_info >= (3, 10):
            ref = ForwardRef(annotation, module=module)
        else:
            ref = ForwardRef(annotation)
        annotation = ref._evaluate(globalns, globalns, recursive_guard=frozenset())  # noqa
    return annotation


def get_typed_parameters(obj: Callable[..., Any]) -> list[inspect.Parameter]:
    """Get the typed parameters of a callable object."""
    globalns = getattr(obj, "__globals__", {})
    module = getattr(obj, "__module__", None)
    return [
        parameter.replace(
            annotation=get_typed_annotation(
                parameter.annotation, globalns, module=module
            )
        )
        for parameter in inspect.signature(obj).parameters.values()
    ]


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
