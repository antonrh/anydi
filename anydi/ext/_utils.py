"""AnyDI FastAPI extension."""

from __future__ import annotations

import inspect
import logging
from typing import Annotated, Any, Callable

from typing_extensions import get_args, get_origin

from anydi._container import Container

logger = logging.getLogger(__name__)


class HasInterface:
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

    origin, *metadata = get_args(parameter.annotation)
    default = metadata[-1]

    if not isinstance(default, HasInterface):
        return parameter

    new_metadata = metadata[:-1]

    if new_metadata:
        interface = Annotated.__class_getitem__((origin, *metadata[:-1]))  # type: ignore
    else:
        interface = origin

    return parameter.replace(annotation=interface, default=default)


def patch_call_parameter(
    container: Container, call: Callable[..., Any], parameter: inspect.Parameter
) -> None:
    """Patch a parameter to inject dependencies using AnyDI."""
    parameter = patch_annotated_parameter(parameter)

    if not isinstance(parameter.default, HasInterface):
        return None

    container._validate_injected_parameter(call, parameter)  # noqa

    parameter.default.interface = parameter.annotation
