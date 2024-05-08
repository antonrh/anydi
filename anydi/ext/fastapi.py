"""AnyDI FastAPI extension."""

from __future__ import annotations

import inspect
import logging
from typing import Any, Callable, Iterator, cast

from fastapi import Depends, FastAPI, params
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from starlette.requests import Request
from typing_extensions import Annotated, get_args, get_origin

from anydi import Container
from anydi._utils import get_full_qualname, get_typed_parameters

from .starlette.middleware import RequestScopedMiddleware

__all__ = ["RequestScopedMiddleware", "install", "get_container", "Inject"]

logger = logging.getLogger(__name__)


def install(app: FastAPI, container: Container) -> None:
    """Install AnyDI into a FastAPI application.

    Args:
        app: The FastAPI application instance.
        container: The container.

    This function installs the AnyDI container into a FastAPI application by attaching
    it to the application state. It also patches the route dependencies to inject the
    required dependencies using AnyDI.
    """
    app.state.container = container  # noqa

    patched = []

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for dependant in _iter_dependencies(route.dependant):
            if dependant.cache_key in patched:
                continue
            patched.append(dependant.cache_key)
            call, *params = dependant.cache_key
            if not call:
                continue  # pragma: no cover
            for parameter in get_typed_parameters(call):
                _patch_route_parameter(call, parameter, container)


def get_container(request: Request) -> Container:
    """Get the AnyDI container from a FastAPI request.

    Args:
        request: The FastAPI request.

    Returns:
        The AnyDI container associated with the request.
    """
    return cast(Container, request.app.state.container)


class Resolver(params.Depends):
    """Parameter dependency class for injecting dependencies using AnyDI."""

    def __init__(self) -> None:
        super().__init__(dependency=self._dependency, use_cache=True)
        self._interface: Any = None

    @property
    def interface(self) -> Any:
        if self._interface is None:
            raise TypeError("Interface is not set.")
        return self._interface

    @interface.setter
    def interface(self, interface: Any) -> None:
        self._interface = interface

    async def _dependency(self, container: Container = Depends(get_container)) -> Any:
        return await container.aresolve(self.interface)


def Inject() -> Any:  # noqa
    """Decorator for marking a function parameter as requiring injection.

    The `Inject` decorator is used to mark a function parameter as requiring injection
    of a dependency resolved by AnyDI.

    Returns:
        The `Resolver` instance representing the parameter dependency.
    """
    return Resolver()


def _iter_dependencies(dependant: Dependant) -> Iterator[Dependant]:
    """Iterate over the dependencies of a dependant."""
    yield dependant
    if dependant.dependencies:
        for sub_dependant in dependant.dependencies:
            yield from _iter_dependencies(sub_dependant)


def _patch_route_parameter(
    call: Callable[..., Any], parameter: inspect.Parameter, container: Container
) -> None:
    """Patch a parameter to inject dependencies using AnyDI.

    Args:
        call:  The call function.
        parameter: The parameter to patch.
        container: The AnyDI container.
    """
    parameter = _patch_annotated_parameter(parameter)

    if not isinstance(parameter.default, Resolver):
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


def _patch_annotated_parameter(parameter: inspect.Parameter) -> inspect.Parameter:
    """Patch an annotated parameter to resolve the default value."""
    if not (
        get_origin(parameter.annotation) is Annotated
        and parameter.default is parameter.empty
    ):
        return parameter

    tp_origin, *tp_metadata = get_args(parameter.annotation)
    default = tp_metadata[-1]

    if not isinstance(default, Resolver):
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
