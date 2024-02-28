"""AnyDI FastAPI extension."""

from typing import Any, Iterator, cast

from fastapi import Depends, FastAPI, params
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from starlette.requests import Request

from anydi import Container
from anydi._utils import get_signature

from ._utils import HasInterface, patch_parameter_interface
from .starlette.middleware import RequestScopedMiddleware

__all__ = ["RequestScopedMiddleware", "install", "get_container", "Inject"]


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
            for parameter in get_signature(call).parameters.values():
                patch_parameter_interface(call, parameter, container)


def get_container(request: Request) -> Container:
    """Get the AnyDI container from a FastAPI request.

    Args:
        request: The FastAPI request.

    Returns:
        The AnyDI container associated with the request.
    """
    return cast(Container, request.app.state.container)


class Resolver(params.Depends, HasInterface):
    """Parameter dependency class for injecting dependencies using AnyDI."""

    def __init__(self) -> None:
        super().__init__(dependency=self._dependency, use_cache=True)
        HasInterface.__init__(self)

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
