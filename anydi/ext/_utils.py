import inspect
from typing import Any, Callable

from typing_extensions import Annotated, get_args, get_origin

from anydi import Container
from anydi._logger import logger
from anydi._utils import get_full_qualname


class HasInterface:
    def __init__(self) -> None:
        self._interface: Any = None

    @property
    def interface(self) -> Any:
        if self._interface is None:
            raise TypeError("Interface is not set.")
        return self._interface

    @interface.setter
    def interface(self, interface: Any) -> None:
        self._interface = interface


def patch_parameter_interface(
    call: Callable[..., Any], parameter: inspect.Parameter, container: Container
) -> None:
    """Patch a parameter to inject dependencies using AnyDI.

    Args:
        call:  The call function.
        parameter: The parameter to patch.
        container: The AnyDI container.
    """
    interface, default = parameter.annotation, parameter.default

    if get_origin(interface) is Annotated:
        args = get_args(interface)
        if len(args) == 2:
            interface, default = args
        elif len(args) == 3:
            interface, metadata, default = args
            interface = Annotated[interface, metadata]

    if not isinstance(default, HasInterface):
        return None

    parameter = parameter.replace(annotation=interface, default=default)

    if not container.strict and not container.is_registered(interface):
        logger.debug(
            f"Callable `{get_full_qualname(call)}` injected parameter "
            f"`{parameter.name}` with an annotation of "
            f"`{get_full_qualname(interface)}` "
            "is not registered. It will be registered at runtime with the "
            "first call because it is running in non-strict mode."
        )
    else:
        container._validate_injected_parameter(call, parameter)  # noqa

    parameter.default.interface = parameter.annotation
