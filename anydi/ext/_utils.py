"""AnyDI FastAPI extension."""

from __future__ import annotations

import inspect
import logging
from functools import wraps
from typing import Any, Callable

from typing_extensions import Annotated, get_args, get_origin

from anydi import Container
from anydi._utils import get_full_qualname

logger = logging.getLogger(__name__)


class HasInterface:
    _interface: Any = None

    @property
    def interface(self) -> Any:
        if self._interface is None:
            raise TypeError("Interface is not set.")
        return self._interface

    @interface.setter
    def interface(self, interface: Any) -> None:
        self._interface = interface


def patch_annotated_parameter(parameter: inspect.Parameter) -> inspect.Parameter:
    """Patch an annotated parameter to resolve the default value."""
    if not (
        get_origin(parameter.annotation) is Annotated
        and parameter.default is parameter.empty
    ):
        return parameter

    tp_origin, *tp_metadata = get_args(parameter.annotation)
    default = tp_metadata[-1]

    if not isinstance(default, HasInterface):
        return parameter

    if (num := len(tp_metadata[:-1])) == 0:
        interface = tp_origin
    elif num == 1:
        interface = Annotated[tp_origin, tp_metadata[0]]
    elif num == 2:
        interface = Annotated[tp_origin, tp_metadata[0], tp_metadata[1]]
    elif num == 3:
        interface = Annotated[
            tp_origin,
            tp_metadata[0],
            tp_metadata[1],
            tp_metadata[2],
        ]
    else:
        raise TypeError("Too many annotated arguments.")  # pragma: no cover
    return parameter.replace(annotation=interface, default=default)


def patch_call_parameter(
    call: Callable[..., Any], parameter: inspect.Parameter, container: Container
) -> None:
    """Patch a parameter to inject dependencies using AnyDI.

    Args:
        call:  The call function.
        parameter: The parameter to patch.
        container: The AnyDI container.
    """
    parameter = patch_annotated_parameter(parameter)

    if not isinstance(parameter.default, HasInterface):
        return None

    if not container.strict and not container.is_registered(parameter.annotation):
        logger.debug(
            f"Callable `{get_full_qualname(call)}` injected parameter "
            f"`{parameter.name}` with an annotation of "
            f"`{get_full_qualname(parameter.annotation)}` "
            "is not registered. It will be registered at runtime with the "
            "first call because it is running in non-strict mode."
        )
    else:
        container._validate_injected_parameter(call, parameter)  # noqa

    parameter.default.interface = parameter.annotation


def _any_typed_interface(interface: Any, prefix: str) -> Any:
    origin = get_origin(interface)
    if origin is not Annotated:
        return interface  # pragma: no cover
    named = interface.__metadata__[-1]

    if isinstance(named, str) and named.startswith(prefix):
        _, setting_name = named.rsplit(prefix, maxsplit=1)
        return Annotated[Any, f"{prefix}{setting_name}"]
    return interface


def patch_any_typed_annotated(container: Container, *, prefix: str) -> None:
    def _patched_resolve(resolve: Any) -> Any:
        @wraps(resolve)
        def wrapper(interface: Any) -> Any:
            return resolve(_any_typed_interface(interface, prefix))

        return wrapper

    def _patched_aresolve(resolve: Any) -> Any:
        @wraps(resolve)
        async def wrapper(interface: Any) -> Any:
            return await resolve(_any_typed_interface(interface, prefix))

        return wrapper

    container.resolve = _patched_resolve(  # type: ignore[method-assign]
        container.resolve
    )
    container.aresolve = _patched_aresolve(  # type: ignore[method-assign]
        container.aresolve
    )
