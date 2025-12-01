"""AnyDI FastAPI extension."""

from __future__ import annotations

import inspect
from collections.abc import Iterator
from typing import Annotated, Any, cast

from fastapi import Depends, FastAPI, params
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from starlette.requests import Request

from anydi import Container, Inject
from anydi._types import ProvideMarker, set_provide_factory

from .starlette.middleware import RequestScopedMiddleware

__all__ = ["install", "get_container", "Inject", "RequestScopedMiddleware"]


def get_container(request: Request) -> Container:
    """Get the AnyDI container from a FastAPI request."""
    return cast(Container, request.app.state.container)


class _ProvideMarker(params.Depends, ProvideMarker):
    def __init__(self) -> None:
        super().__init__(dependency=self._dependency, use_cache=True)
        ProvideMarker.__init__(self)

    async def _dependency(
        self, container: Annotated[Container, Depends(get_container)]
    ) -> Any:
        return await container.aresolve(self.interface)


# Configure Inject() and Provide[T] to use FastAPI-specific marker
set_provide_factory(_ProvideMarker)


def _iter_dependencies(dependant: Dependant) -> Iterator[Dependant]:
    yield dependant
    if dependant.dependencies:
        for sub_dependant in dependant.dependencies:
            yield from _iter_dependencies(sub_dependant)


def _validate_route_dependencies(
    route: APIRoute, container: Container, patched: set[tuple[Any, ...]]
) -> None:
    for dependant in _iter_dependencies(route.dependant):
        if dependant.cache_key in patched:
            continue
        patched.add(dependant.cache_key)
        call, *_ = dependant.cache_key
        if not call:
            continue  # pragma: no cover
        for parameter in inspect.signature(call, eval_str=True).parameters.values():
            container.validate_injected_parameter(parameter, call=call)


def install(app: FastAPI, container: Container) -> None:
    """Install AnyDI into a FastAPI application."""
    app.state.container = container  # noqa
    patched: set[tuple[Any, ...]] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        _validate_route_dependencies(route, container, patched)
