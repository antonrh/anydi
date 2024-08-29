"""Shared AnyDI utils module."""

from __future__ import annotations

import builtins
import functools
import importlib
import inspect
import sys
from typing import Any, AsyncIterator, Callable, ForwardRef, Iterator, TypeVar

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


def evaluate_forwardref(type_: ForwardRef, globalns: Any, localns: Any) -> Any:
    if sys.version_info < (3, 9):
        return type_._evaluate(globalns, localns)
    return type_._evaluate(globalns, localns, recursive_guard=frozenset())


def get_typed_annotation(
    annotation: Any,
    globalns: dict[str, Any],
    module: Any = None,
    is_class: bool = False,
) -> Any:
    """Get the typed annotation of a parameter."""
    if isinstance(annotation, str):
        if sys.version_info >= (3, 10, 2):
            annotation = ForwardRef(annotation, module=module, is_class=is_class)
        elif sys.version_info >= (3, 10, 0):
            annotation = ForwardRef(annotation, module=module)
        else:
            annotation = ForwardRef(annotation)
        annotation = evaluate_forwardref(annotation, globalns, {})
    return annotation


def get_typed_return_annotation(obj: Callable[..., Any]) -> Any:
    """Get the typed return annotation of a callable object."""
    signature = inspect.signature(obj)
    annotation = signature.return_annotation
    if annotation is inspect.Signature.empty:
        return None
    globalns = getattr(obj, "__globals__", {})
    module = getattr(obj, "__module__", None)
    is_class = inspect.isclass(obj)
    return get_typed_annotation(annotation, globalns, module=module, is_class=is_class)


def get_typed_parameters(obj: Callable[..., Any]) -> list[inspect.Parameter]:
    """Get the typed parameters of a callable object."""
    globalns = getattr(obj, "__globals__", {})
    module = getattr(obj, "__module__", None)
    is_class = inspect.isclass(obj)
    return [
        parameter.replace(
            annotation=get_typed_annotation(
                parameter.annotation,
                globalns,
                module=module,
                is_class=is_class,
            )
        )
        for name, parameter in inspect.signature(obj).parameters.items()
    ]


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
