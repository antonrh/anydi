"""AnyDI FastAPI extension."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated, Any, cast

from fastapi import Depends, FastAPI, params
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from starlette.requests import Request

from anydi._container import Container
from anydi._typing import InjectMarker, get_typed_parameters

from .starlette.middleware import RequestScopedMiddleware

__all__ = ["RequestScopedMiddleware", "install", "get_container", "Inject"]


def install(app: FastAPI, container: Container) -> None:
    """Install AnyDI into a FastAPI application.

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
                container.validate_injected_parameter(parameter, call=call)


def get_container(request: Request) -> Container:
    """Get the AnyDI container from a FastAPI request."""
    return cast(Container, request.app.state.container)


class _Inject(params.Depends, InjectMarker):
    def __init__(self) -> None:
        super().__init__(dependency=self._dependency, use_cache=True)
        InjectMarker.__init__(self)

    async def _dependency(
        self, container: Annotated[Container, Depends(get_container)]
    ) -> Any:
        return await container.aresolve(self.interface)


def Inject() -> Any:
    return _Inject()


def _iter_dependencies(dependant: Dependant) -> Iterator[Dependant]:
    """Iterate over the dependencies of a dependant."""
    yield dependant
    if dependant.dependencies:
        for sub_dependant in dependant.dependencies:
            yield from _iter_dependencies(sub_dependant)
