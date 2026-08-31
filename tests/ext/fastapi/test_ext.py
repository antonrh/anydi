from collections.abc import Iterator
from typing import Annotated, Any

import pytest
from fastapi import APIRouter, Depends, FastAPI, WebSocket
from starlette.middleware import Middleware
from starlette.testclient import TestClient

import anydi.ext.fastapi
from anydi import Container, Inject, Provide
from anydi.ext.fastapi import get_container
from anydi.ext.starlette.middleware import RequestScopedMiddleware


def test_install_without_annotation() -> None:
    container = Container()

    @container.provider(scope="singleton")
    def message() -> str:
        return "Hello"

    app = FastAPI()

    @app.get("/hello")
    def say_hello(message=Inject()) -> Any:  # type: ignore[no-untyped-def]
        return message

    with pytest.raises(
        TypeError, match=r"Missing `(.*?).say_hello` parameter `message` annotation."
    ):
        anydi.ext.fastapi.install(app, container)


def test_install_unknown_annotation() -> None:
    container = Container()

    app = FastAPI()

    @app.get("/hello")
    def say_hello(message: str = Inject()) -> Any:
        return message

    with pytest.raises(
        LookupError,
        match=(
            r"`(.*?).say_hello` has an unknown dependency parameter `message` "
            "with an annotation of `str`."
        ),
    ):
        anydi.ext.fastapi.install(app, container)


def test_install_with_included_router() -> None:
    """Test that dependencies on routes added via include_router are injected."""
    container = Container()

    @container.provider(scope="singleton")
    def message() -> str:
        return "Hello from router"

    router = APIRouter()

    @router.get("/router-hello")
    def say_hello(message: str = Inject()) -> Any:
        return message

    @router.get("/router-hello-provide")
    def say_hello_provide(message: Provide[str]) -> Any:
        return message

    app = FastAPI()
    app.include_router(router, prefix="/api")

    # Install after including the router so the merged routes are validated
    anydi.ext.fastapi.install(app, container)

    client = TestClient(app)

    assert client.get("/api/router-hello").json() == "Hello from router"
    assert client.get("/api/router-hello-provide").json() == "Hello from router"


def test_install_with_nested_included_routers() -> None:
    """Test injection through routers nested via include_router."""
    container = Container()

    @container.provider(scope="singleton")
    def message() -> str:
        return "nested"

    inner = APIRouter()

    @inner.get("/leaf")
    def leaf(message: str = Inject()) -> Any:
        return message

    outer = APIRouter()
    outer.include_router(inner, prefix="/inner")

    app = FastAPI()
    app.include_router(outer, prefix="/outer")

    anydi.ext.fastapi.install(app, container)

    client = TestClient(app)

    assert client.get("/outer/inner/leaf").json() == "nested"


def test_install_validates_included_router_unknown_annotation() -> None:
    """Routes from an included router are validated during install."""
    container = Container()

    router = APIRouter()

    @router.get("/hello")
    def say_hello(message: str = Inject()) -> Any:
        return message

    app = FastAPI()
    app.include_router(router)

    with pytest.raises(
        LookupError,
        match=(
            r"`(.*?).say_hello` has an unknown dependency parameter `message` "
            "with an annotation of `str`."
        ),
    ):
        anydi.ext.fastapi.install(app, container)


def test_install_with_mounted_app() -> None:
    """Routes of a mounted application resolve through the outer container."""
    container = Container()

    @container.provider(scope="singleton")
    def message() -> str:
        return "mounted"

    sub = FastAPI()

    @sub.get("/leaf")
    def leaf(message: Provide[str]) -> Any:
        return message

    app = FastAPI(middleware=[Middleware(RequestScopedMiddleware, container=container)])
    app.mount("/sub", sub)

    anydi.ext.fastapi.install(app, container)

    client = TestClient(app)

    assert client.get("/sub/leaf").json() == "mounted"


def test_install_keeps_container_of_mounted_app() -> None:
    """A mounted application installed with its own container keeps it."""
    outer = Container()
    inner = Container()

    @inner.provider(scope="singleton")
    def message() -> str:
        return "inner"

    sub = FastAPI()
    anydi.ext.fastapi.install(sub, inner)

    app = FastAPI()
    app.mount("/sub", sub)
    anydi.ext.fastapi.install(app, outer)

    assert sub.state.container is inner


def test_install_validates_routes_added_later() -> None:
    """A route added after install is validated as it is added."""
    container = Container()

    @container.provider(scope="singleton")
    def message() -> str:
        return "late"

    app = FastAPI(middleware=[Middleware(RequestScopedMiddleware, container=container)])

    anydi.ext.fastapi.install(app, container)

    @app.get("/late")
    def late(message: Provide[str]) -> Any:
        return message

    router = APIRouter()

    @router.get("/late-router")
    def late_router(message: str = Inject()) -> Any:
        return message

    app.include_router(router)

    client = TestClient(app)

    assert client.get("/late").json() == "late"
    assert client.get("/late-router").json() == "late"


def test_install_validates_route_added_later_unknown_annotation() -> None:
    """A route added after install fails the same way as one added before."""
    container = Container()
    app = FastAPI()

    anydi.ext.fastapi.install(app, container)

    with pytest.raises(
        LookupError,
        match=(
            r"`(.*?).say_hello` has an unknown dependency parameter `message` "
            "with an annotation of `str`."
        ),
    ):

        @app.get("/hello")
        def say_hello(message: str = Inject()) -> Any:
            return message


def test_get_container_without_install() -> None:
    """The error names what to call instead of raising an AttributeError."""
    app = FastAPI()

    @app.get("/hello")
    def say_hello(container: Annotated[Container, Depends(get_container)]) -> Any:
        return str(container)

    client = TestClient(app, raise_server_exceptions=True)

    with pytest.raises(RuntimeError, match="No container is installed"):
        client.get("/hello")


def test_install_registers_websocket_scope() -> None:
    """Test that websocket scope is automatically registered during install."""
    # Create a fresh container without websocket scope
    container = Container()
    app = FastAPI()

    # Verify scope doesn't exist before install
    assert "websocket" not in container._scopes

    anydi.ext.fastapi.install(app, container)

    # Verify scope exists after install
    assert "websocket" in container._scopes


def test_install_websocket_resource_cleanup() -> None:
    """Test that websocket-scoped resources are properly cleaned up."""
    container = Container()
    container.register_scope("websocket", parents=["request"])
    cleanup_called: list[str] = []

    @container.provider(scope="websocket")
    def cleanup_resource() -> Iterator[str]:
        cleanup_called.append("setup")
        yield "resource"
        cleanup_called.append("cleanup")

    app = FastAPI(
        middleware=[
            Middleware(RequestScopedMiddleware, container=container),
        ]
    )

    @app.websocket("/ws/resource")
    async def websocket_resource(
        websocket: WebSocket,
        resource: Annotated[str, Inject()],
    ) -> None:
        await websocket.accept()
        await websocket.send_text(f"Got: {resource}")
        await websocket.close()

    # Install after defining routes so it can validate them
    anydi.ext.fastapi.install(app, container)

    client = TestClient(app)

    # Before connection
    assert cleanup_called == []

    # During connection
    with client.websocket_connect("/ws/resource") as websocket:
        response = websocket.receive_text()
        assert response == "Got: resource"
        # Setup called
        assert "setup" in cleanup_called

    # After connection closed
    assert cleanup_called == ["setup", "cleanup"]
