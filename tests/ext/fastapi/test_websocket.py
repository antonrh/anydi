"""Tests for FastAPI WebSocket support."""

from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import FastAPI, WebSocket
from starlette.middleware import Middleware
from starlette.testclient import TestClient

import anydi.ext.fastapi
from anydi import Container, Inject
from anydi.ext.starlette.middleware import RequestScopedMiddleware
from anydi.ext.starlette.websocket_middleware import WebSocketScopedMiddleware

from tests.ext.fixtures import MailService


class ConnectionState:
    """WebSocket-scoped connection state."""

    def __init__(self) -> None:
        self.message_count = 0

    def process(self, message: str) -> str:
        self.message_count += 1
        return f"Message #{self.message_count}: {message}"


class WebSocketLogger:
    """Singleton logger shared across all connections."""

    def __init__(self) -> None:
        self.connections: list[str] = []

    def log_connection(self, client_id: str) -> None:
        self.connections.append(client_id)


@pytest.fixture
def container() -> Container:
    """Create a container with WebSocket providers."""
    # Ensure FastAPI's provide factory is set for this test
    from anydi._types import set_provide_factory
    from anydi.ext.fastapi import _ProvideMarker

    set_provide_factory(_ProvideMarker)

    container = Container()

    # Register websocket scope first
    container.register_scope("websocket")

    # WebSocket-scoped provider - one per connection
    @container.provider(scope="websocket")
    def connection_state() -> ConnectionState:
        return ConnectionState()

    # Singleton provider - shared across all connections
    @container.provider(scope="singleton")
    def websocket_logger() -> WebSocketLogger:
        return WebSocketLogger()

    # Singleton mail service
    @container.provider(scope="singleton")
    def mail_service() -> MailService:
        return MailService()

    return container


@pytest.fixture
def app(container: Container) -> FastAPI:
    """Create a FastAPI app with WebSocket support."""

    app = FastAPI(
        middleware=[
            Middleware(RequestScopedMiddleware, container=container),
            Middleware(WebSocketScopedMiddleware, container=container),
        ]
    )

    @app.websocket("/ws/echo")
    async def websocket_echo(
        websocket: WebSocket,
        state: Annotated[ConnectionState, Inject()],
    ) -> None:
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_text()
                if data == "quit":
                    break
                response = state.process(data)
                await websocket.send_text(response)
        finally:
            await websocket.close()

    @app.websocket("/ws/logger")
    async def websocket_logger_endpoint(
        websocket: WebSocket,
        logger: Annotated[WebSocketLogger, Inject()],
    ) -> None:
        await websocket.accept()
        client_id = await websocket.receive_text()
        logger.log_connection(client_id)
        await websocket.send_text(f"Logged: {client_id}")
        await websocket.close()

    @app.websocket("/ws/mail")
    async def websocket_mail(
        websocket: WebSocket,
        mail_service: Annotated[MailService, Inject()],
    ) -> None:
        await websocket.accept()
        message = await websocket.receive_text()
        mail = await mail_service.send_mail("ws@example.com", message)
        await websocket.send_json({"email": mail.email, "message": mail.message})
        await websocket.close()

    anydi.ext.fastapi.install(app, container)

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client."""
    return TestClient(app)


def test_basic_websocket_with_injection(client: TestClient) -> None:
    """Test basic WebSocket connection with dependency injection."""
    with client.websocket_connect("/ws/echo") as websocket:
        websocket.send_text("hello")
        response = websocket.receive_text()
        assert response == "Message #1: hello"

        websocket.send_text("world")
        response = websocket.receive_text()
        assert response == "Message #2: world"

        websocket.send_text("quit")


def test_websocket_scoped_dependencies_same_connection(client: TestClient) -> None:
    """Test that websocket-scoped dependencies maintain state across messages."""
    with client.websocket_connect("/ws/echo") as websocket:
        # Send multiple messages - state should be preserved
        websocket.send_text("first")
        assert websocket.receive_text() == "Message #1: first"

        websocket.send_text("second")
        assert websocket.receive_text() == "Message #2: second"

        websocket.send_text("third")
        assert websocket.receive_text() == "Message #3: third"

        websocket.send_text("quit")


def test_websocket_scoped_dependencies_different_connections(
    client: TestClient,
) -> None:
    """Test that different connections get different scoped instances."""
    # First connection
    with client.websocket_connect("/ws/echo") as websocket1:
        websocket1.send_text("hello")
        response1 = websocket1.receive_text()
        assert response1 == "Message #1: hello"
        websocket1.send_text("quit")

    # Second connection - should start fresh
    with client.websocket_connect("/ws/echo") as websocket2:
        websocket2.send_text("world")
        response2 = websocket2.receive_text()
        assert response2 == "Message #1: world"  # Counter reset!
        websocket2.send_text("quit")


def test_singleton_dependencies_shared_across_connections(
    app: FastAPI, container: Container
) -> None:
    """Test that singleton dependencies are shared across WebSocket connections."""
    client = TestClient(app)

    # Get the singleton logger to verify connections
    logger = container.resolve(WebSocketLogger)

    # First connection
    with client.websocket_connect("/ws/logger") as websocket1:
        websocket1.send_text("client-1")
        response1 = websocket1.receive_text()
        assert response1 == "Logged: client-1"

    # Second connection
    with client.websocket_connect("/ws/logger") as websocket2:
        websocket2.send_text("client-2")
        response2 = websocket2.receive_text()
        assert response2 == "Logged: client-2"

    # Verify both connections logged to the same singleton
    assert logger.connections == ["client-1", "client-2"]


def test_websocket_with_singleton_service(client: TestClient) -> None:
    """Test injecting singleton service into WebSocket endpoint."""
    with client.websocket_connect("/ws/mail") as websocket:
        websocket.send_text("Hello via WebSocket")
        response = websocket.receive_json()
        assert response == {
            "email": "ws@example.com",
            "message": "Hello via WebSocket",
        }


def test_concurrent_websocket_connections(client: TestClient) -> None:
    """Test multiple concurrent WebSocket connections maintain isolation."""
    # Open two connections simultaneously
    with (
        client.websocket_connect("/ws/echo") as ws1,
        client.websocket_connect("/ws/echo") as ws2,
    ):
        # Send to first connection
        ws1.send_text("connection-1-msg-1")
        assert ws1.receive_text() == "Message #1: connection-1-msg-1"

        # Send to second connection
        ws2.send_text("connection-2-msg-1")
        assert ws2.receive_text() == "Message #1: connection-2-msg-1"

        # Continue with first connection
        ws1.send_text("connection-1-msg-2")
        assert ws1.receive_text() == "Message #2: connection-1-msg-2"

        # Continue with second connection
        ws2.send_text("connection-2-msg-2")
        assert ws2.receive_text() == "Message #2: connection-2-msg-2"

        ws1.send_text("quit")
        ws2.send_text("quit")


def test_websocket_scope_registered_during_install() -> None:
    """Test that websocket scope is automatically registered during install."""
    # Create a fresh container without websocket scope
    container = Container()
    app = FastAPI()

    # Verify scope doesn't exist before install
    assert "websocket" not in container._scopes

    anydi.ext.fastapi.install(app, container)

    # Verify scope exists after install
    assert "websocket" in container._scopes


def test_websocket_with_resource_cleanup() -> None:
    """Test that websocket-scoped resources are properly cleaned up."""
    container = Container()
    container.register_scope("websocket")
    cleanup_called: list[str] = []

    @container.provider(scope="websocket")
    def cleanup_resource() -> Iterator[str]:
        cleanup_called.append("setup")
        yield "resource"
        cleanup_called.append("cleanup")

    app = FastAPI(
        middleware=[
            Middleware(WebSocketScopedMiddleware, container=container),
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
