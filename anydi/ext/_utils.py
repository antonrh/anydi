"""AnyDI FastAPI extension."""

from __future__ import annotations

import inspect
import logging
from typing import Annotated, Any, Callable

from typing_extensions import get_args, get_origin

from anydi import Container
from anydi._typing import _Marker

logger = logging.getLogger(__name__)


class HasInterface(_Marker):
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


def patch_parameter(
    container: Container, parameter: inspect.Parameter, *, call: Callable[..., Any]
) -> None:
    """Patch a parameter to inject dependencies using AnyDI."""
    if (
        get_origin(parameter.annotation) is Annotated
        and parameter.default is inspect.Parameter.empty
    ):
        origin, *metadata = get_args(parameter.annotation)
        default = metadata[-1]
        new_metadata = metadata[:-1]
        if new_metadata:
            interface = Annotated.__class_getitem__((origin, *metadata[:-1]))  # type: ignore
        else:
            interface = origin
        parameter = parameter.replace(annotation=interface, default=default)

    interface, should_inject = container._validate_injected_parameter(
        parameter, call=call
    )  # noqa
    interface, should_inject = container._validate_injected_parameter(
        parameter, call=call
    )  # noqa
    if should_inject:
        parameter.default.interface = interface
    return None
