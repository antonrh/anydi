"""AnyDI FastAPI extension."""

from __future__ import annotations

try:
    import fastapi  # noqa: F401
except ImportError:  # pragma: no cover - CI installs it
    message = "This extension needs `fastapi`. Install it with `pip install fastapi`."
    raise ImportError(message) from None

import functools
import inspect
from collections.abc import Callable, Iterable, Iterator
from typing import Annotated, Any, cast

from fastapi import Depends, FastAPI, params, routing as fastapi_routing
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, APIWebSocketRoute
from starlette.requests import HTTPConnection
from starlette.routing import Mount

from anydi import Container, Inject
from anydi._marker import Marker, extend_marker

from .starlette.middleware import RequestScopedMiddleware

__all__ = ["Inject", "RequestScopedMiddleware", "get_container", "install"]

# FastAPI >= 0.138 wraps `include_router` routes in an `_IncludedRouter` instead
# of flattening them into `app.routes`.
_IncludedRouter: Any = getattr(fastapi_routing, "_IncludedRouter", None)


CONTAINER_SCOPE_KEY = "anydi.container"
"""Where the middleware leaves the container, for apps mounted under others."""


def get_container(connection: HTTPConnection) -> Container:
    container = connection.scope.get(CONTAINER_SCOPE_KEY)
    if container is None:
        # A mounted application has state of its own, which nobody filled.
        container = getattr(connection.app.state, "container", None)
    if container is None:
        raise RuntimeError(
            "No container is installed on this application. Call "
            "`anydi.ext.fastapi.install(app, container)`, and add "
            "`RequestScopedMiddleware` to the outermost application when it "
            "mounts others."
        )
    return cast(Container, container)


class FastAPIMarker(Marker, params.Depends):
    def __init__(self) -> None:
        Marker.__init__(self)
        self._current_owner = "fastapi"
        # Set the framework fields directly instead of calling the (now frozen)
        # params.Depends.__init__; the Marker descriptors route them per-owner.
        self.dependency = self._fastapi_dependency
        self.use_cache = True
        self.scope = None
        self._current_owner = None

    async def _fastapi_dependency(
        self, container: Annotated[Container, Depends(get_container)]
    ) -> Any:
        return await container.aresolve(self.dependency_type)


# Composes with a marker another extension installed, so both keep working.
extend_marker(FastAPIMarker)


def _iter_routes(
    routes: Iterable[Any],
) -> Iterator[APIRoute | APIWebSocketRoute]:
    """Yield all API routes, descending into included routers and mounted apps."""
    for route in routes:
        if isinstance(route, APIRoute | APIWebSocketRoute):
            yield route
        elif _IncludedRouter is not None and isinstance(route, _IncludedRouter):
            yield from _iter_routes(route.original_router.routes)
        elif isinstance(route, Mount):
            yield from _iter_routes(getattr(route.app, "routes", ()))


def _iter_apps(app: Any) -> Iterator[Any]:
    """Yield the application and every application mounted under it."""
    yield app
    for route in getattr(app, "routes", ()):
        if isinstance(route, Mount) and hasattr(route.app, "routes"):
            yield from _iter_apps(route.app)


def _iter_dependencies(dependant: Dependant) -> Iterator[Dependant]:
    yield dependant
    if dependant.dependencies:
        for sub_dependant in dependant.dependencies:
            yield from _iter_dependencies(sub_dependant)


def _dependant_cache_key(dependant: Dependant) -> tuple[Any, ...]:
    """Compute a hashable dedup key (FastAPI 0.140 dropped ``Dependant.cache_key``)."""
    cache_key = getattr(dependant, "cache_key", None)
    if cache_key is not None:
        return cache_key
    scopes = getattr(dependant, "own_oauth_scopes", None) or []
    return (dependant.call, tuple(sorted(set(scopes))))


def _validate_route_dependencies(
    route: APIRoute | APIWebSocketRoute,
    container: Container,
    patched: set[tuple[Any, ...]],
) -> None:
    for dependant in _iter_dependencies(route.dependant):
        cache_key = _dependant_cache_key(dependant)
        if cache_key in patched:
            continue
        patched.add(cache_key)
        call = dependant.call
        if not call:
            continue  # pragma: no cover
        for parameter in inspect.signature(call, eval_str=True).parameters.values():
            _, should_inject, marker = container.validate_injected_parameter(
                parameter, call=call
            )
            if should_inject and marker:
                marker.set_owner("fastapi")


_REGISTERS_ROUTES = (
    "add_api_route",
    "add_api_websocket_route",
    "include_router",
    "mount",
)


def _validate_routes(
    app: FastAPI, container: Container, patched: set[tuple[Any, ...]]
) -> None:
    """Give every marker of every route its owner."""
    for route in _iter_routes(app.routes):
        _validate_route_dependencies(route, container, patched)


def _watch_routes(app: FastAPI, patched: set[tuple[Any, ...]]) -> None:
    """Validate routes added after `install()`, as they are added."""
    if getattr(app.state, "anydi_watching_routes", False):
        return
    app.state.anydi_watching_routes = True
    router = app.router

    def watching(register: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(register)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = register(*args, **kwargs)
            container = getattr(app.state, "container", None)
            if container is not None:
                # `patched` carries over, so only the new routes are inspected.
                _validate_routes(app, container, patched)
            return result

        return wrapper

    for name in _REGISTERS_ROUTES:
        register = getattr(router, name, None)
        if register is not None:
            setattr(router, name, watching(register))


def install(app: FastAPI, container: Container) -> None:
    """Install AnyDI into a FastAPI application."""
    app.state.container = container
    for mounted in _iter_apps(app):
        state = getattr(mounted, "state", None)
        # A sub-application installed with a container of its own keeps it.
        if state is not None and getattr(state, "container", None) is None:
            state.container = container

    # Register websocket scope with request as parent if not already registered
    if not container.has_scope("websocket"):
        container.register_scope("websocket", parents=["request"])

    patched: set[tuple[Any, ...]] = set()
    _validate_routes(app, container, patched)
    _watch_routes(app, patched)
