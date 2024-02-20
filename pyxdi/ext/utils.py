import inspect
import logging
import typing as t

from typing_extensions import Annotated, get_args, get_origin

from pyxdi import PyxDI
from pyxdi.utils import get_full_qualname

logger = logging.getLogger(__name__)


class HasInterface:
    def __init__(self) -> None:
        self._interface: t.Any = None

    @property
    def interface(self) -> t.Any:
        if self._interface is None:
            raise TypeError("Interface is not set.")
        return self._interface

    @interface.setter
    def interface(self, interface: t.Any) -> None:
        self._interface = interface


def patch_parameter_interface(
    call: t.Callable[..., t.Any], parameter: inspect.Parameter, di: PyxDI
) -> None:
    """Patch a parameter to inject dependencies using PyxDI.

    Args:
        call:  The call function.
        parameter: The parameter to patch.
        di: The PyxDI container.
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

    if not di.strict and not di.has_provider(interface):
        logger.debug(
            f"Route `{get_full_qualname(call)}` injected parameter "
            f"`{parameter.name}` with an annotation of "
            f"`{get_full_qualname(interface)}` "
            "is not registered. It will be registered at runtime with the "
            "first call because it is running in non-strict mode."
        )
    else:
        di._validate_injected_parameter(call, parameter)  # noqa

    parameter.default.interface = parameter.annotation
