"""Shared AnyDI utils module."""

from __future__ import annotations

import builtins
import functools
import inspect
import sys
from typing import Any, AsyncIterator, Callable, ForwardRef, Iterator, TypeVar, cast

from typing_extensions import Annotated, ParamSpec, get_origin

try:
    import anyio  # noqa
except ImportError:
    anyio = None  # type: ignore[assignment]


if sys.version_info < (3, 9):  # pragma: nocover

    def evaluate_forwardref(type_: ForwardRef, globalns: Any, localns: Any) -> Any:
        return type_._evaluate(globalns, localns)  # noqa

else:

    def evaluate_forwardref(type_: ForwardRef, globalns: Any, localns: Any) -> Any:
        return cast(Any, type_)._evaluate(globalns, localns, set())  # noqa


T = TypeVar("T")
P = ParamSpec("P")


def get_full_qualname(obj: Any) -> str:
    """Get the fully qualified name of an object."""
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


def is_builtin_type(tp: type[Any]) -> bool:
    """Check if the given type is a built-in type."""
    return tp.__module__ == builtins.__name__


def make_forwardref(annotation: str, globalns: dict[str, Any]) -> Any:
    """Create a forward reference from a string annotation."""
    forward_ref = ForwardRef(annotation)
    return evaluate_forwardref(forward_ref, globalns, globalns)


def get_typed_annotation(annotation: Any, globalns: dict[str, Any]) -> Any:
    """Get the typed annotation of a parameter."""
    if isinstance(annotation, str):
        annotation = ForwardRef(annotation)
        annotation = evaluate_forwardref(annotation, globalns, globalns)
    return annotation


def get_typed_return_annotation(obj: Callable[..., Any]) -> Any:
    """Get the typed return annotation of a callable object."""
    signature = inspect.signature(obj)
    annotation = signature.return_annotation
    if annotation is inspect.Signature.empty:
        return None
    globalns = getattr(obj, "__globals__", {})
    return get_typed_annotation(annotation, globalns)


def get_typed_parameters(obj: Callable[..., Any]) -> list[inspect.Parameter]:
    """Get the typed parameters of a callable object."""
    globalns = getattr(obj, "__globals__", {})
    return [
        parameter.replace(
            annotation=get_typed_annotation(parameter.annotation, globalns)
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
