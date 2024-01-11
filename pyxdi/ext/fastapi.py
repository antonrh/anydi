"""PyxDI FastAPI extension."""
import logging
import typing as t

from fastapi import Depends, FastAPI, params
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from starlette.requests import Request

from pyxdi import PyxDI
from pyxdi.ext.starlette.middleware import RequestScopedMiddleware
from pyxdi.utils import get_full_qualname, get_signature

__all__ = ["RequestScopedMiddleware", "install", "get_di", "Inject"]

logger = logging.getLogger(__name__)


def install(app: FastAPI, di: PyxDI) -> None:
    """Install PyxDI into a FastAPI application.

    Args:
        app: The FastAPI application instance.
        di: The PyxDI container.

    This function installs the PyxDI container into a FastAPI application by attaching
    it to the application state. It also patches the route dependencies to inject the
    required dependencies using PyxDI.
    """
    app.state.di = di  # noqa

    patched = []

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for dependant in iter_dependencies(route.dependant):
            if dependant.cache_key in patched:
                continue
            patched.append(dependant.cache_key)
            call, *params = dependant.cache_key
            if not call:
                continue  # pragma: no cover
            for parameter in get_signature(call).parameters.values():
                if not isinstance(parameter.default, InjectParam):
                    continue
                if di.auto_register and not di.has_provider(parameter.annotation):
                    logger.info(
                        f"Route `{get_full_qualname(call)}` injected parameter "
                        f"`{parameter.name}` with an annotation of "
                        f"`{get_full_qualname(parameter.annotation)}` "
                        "is not registered. It will be registered at runtime with the "
                        "first call because it is running with auto_register mode."
                    )
                else:
                    di._validate_injected_parameter(call, parameter)  # noqa

                parameter.default.interface = parameter.annotation


def get_di(request: Request) -> PyxDI:
    """Get the PyxDI container from a FastAPI request.

    Args:
        request: The FastAPI request.

    Returns:
        The PyxDI container associated with the request.
    """
    return t.cast(PyxDI, request.app.state.di)


class InjectParam(params.Depends):
    """Parameter dependency class for injecting dependencies using PyxDI."""

    def __init__(self) -> None:
        super().__init__(dependency=self._dependency, use_cache=True)
        self._interface: t.Any = None

    @property
    def interface(self) -> t.Any:
        if self._interface is None:
            raise TypeError("Interface is not set.")
        return self._interface

    @interface.setter
    def interface(self, val: t.Any) -> None:
        self._interface = val

    async def _dependency(self, di: PyxDI = Depends(get_di)) -> t.Any:
        return await di.aget_instance(self.interface)


def Inject() -> t.Any:  # noqa
    """Decorator for marking a function parameter as requiring injection.

    The `Inject` decorator is used to mark a function parameter as requiring injection
    of a dependency resolved by PyxDI.

    Returns:
        The `InjectParam` instance representing the parameter dependency.
    """
    return InjectParam()


def iter_dependencies(dependant: Dependant) -> t.Iterator[Dependant]:
    yield dependant
    if dependant.dependencies:
        for sub_dependant in dependant.dependencies:
            yield from iter_dependencies(sub_dependant)
