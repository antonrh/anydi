"""AnyDI FastAPI extension."""

from __future__ import annotations

import inspect
import logging
from typing import Annotated, Any, Callable

from typing_extensions import get_args, get_origin

from anydi import Container
from anydi._typing import _InjectMarker

logger = logging.getLogger(__name__)


class HasInterface(_InjectMarker):
    __slots__ = ("_interface",)

    def __init__(self, interface: Any = None) -> None:
        self._interface = interface

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
        and parameter.default is inspect.Parameter.empty
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
    container: Container, call: Callable[..., Any], parameter: inspect.Parameter
) -> None:
    """Patch a parameter to inject dependencies using AnyDI."""
    parameter = patch_annotated_parameter(parameter)

    interface, should_inject = container._validate_injected_parameter(
        parameter, call=call
    )  # noqa
    if should_inject:
        parameter.default.interface = interface
    return None
