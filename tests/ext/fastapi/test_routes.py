from unittest import mock

from starlette.testclient import TestClient

from anydi import Container

from tests.ext.fastapi.app import WebSocketLogger
from tests.ext.fixtures import TEST_EMAIL, Mail, MailService, User, UserService


def test_send_mail(client: TestClient) -> None:
    message = "test"

    response = client.post("/send-mail", json={"message": message})

    assert response.status_code == 200
    assert response.json() == {
        "email": TEST_EMAIL,
        "message": message,
    }


def test_send_mail_with_mocked_mail_service(
    client: TestClient, container: Container
) -> None:
    mail = Mail(email="mock@mail.com", message="mock")

    mail_service_mock = mock.MagicMock(spec=MailService)
    mail_service_mock.send_mail.return_value = mail

    with container.override(MailService, instance=mail_service_mock):
        response = client.post("/send-mail", json={"message": mail.message})

    assert response.status_code == 200
    assert response.json() == {
        "email": mail.email,
        "message": mail.message,
    }


def test_send_mail_with_mocked_user_service(
    client: TestClient, container: Container
) -> None:
    user = User(id=100, email="mock@mail.com")
    message = "hello"

    user_service_mock = mock.MagicMock(spec=UserService)
    user_service_mock.get_user.return_value = user

    with container.override(UserService, instance=user_service_mock):
        response = client.post("/send-mail", json={"message": message})

    assert response.status_code == 200
    assert response.json() == {
        "email": user.email,
        "message": message,
    }


def test_send_mail_with_annotated_params(client: TestClient) -> None:
    message = "test"

    response = client.post("/send-mail-annotated", json={"message": message})

    assert response.status_code == 200
    assert response.json() == {
        "email": TEST_EMAIL,
        "message": message,
    }


def test_send_mail_with_provide(client: TestClient) -> None:
    message = "test"

    response = client.post("/send-mail-provide", json={"message": message})

    assert response.status_code == 200
    assert response.json() == {
        "email": TEST_EMAIL,
        "message": message,
    }


def test_route_annotated_mixed_markers(client: TestClient) -> None:
    first_response = client.get("/annotated-mixed")

    assert first_response.status_code == 200
    first_json = first_response.json()
    assert first_json["default"] == "Hello from the default message!"
    assert first_json["vip"] == "Hello VIP!"
    assert first_json["request"].startswith("Request scoped message #")

    second_json = client.get("/annotated-mixed").json()
    assert second_json["request"].startswith("Request scoped message #")
    assert second_json["request"] != first_json["request"]


def test_websocket_basic_injection(client: TestClient) -> None:
    """Test basic WebSocket connection with dependency injection."""
    with client.websocket_connect("/ws/echo") as websocket:
        websocket.send_text("hello")
        response = websocket.receive_text()
        assert response == "Message #1: hello"

        websocket.send_text("world")
        response = websocket.receive_text()
        assert response == "Message #2: world"

        websocket.send_text("quit")


def test_websocket_scoped_state_persists_across_messages(client: TestClient) -> None:
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


def test_websocket_scoped_state_isolated_between_connections(
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


def test_websocket_singleton_shared_across_connections(
    container: Container, client: TestClient
) -> None:
    """Test that singleton dependencies are shared across WebSocket connections."""
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


def test_websocket_singleton_service(client: TestClient) -> None:
    """Test injecting singleton service into WebSocket endpoint."""
    with client.websocket_connect("/ws/mail") as websocket:
        websocket.send_text("Hello via WebSocket")
        response = websocket.receive_json()
        assert response == {
            "email": "ws@example.com",
            "message": "Hello via WebSocket",
        }


def test_websocket_request_scoped_dependency(client: TestClient) -> None:
    """Ensure request-scoped dependencies are available to WebSocket handlers."""
    with client.websocket_connect("/ws/request-message") as websocket:
        first_message = websocket.receive_text()
        assert first_message.startswith("Request scoped message #")

    with client.websocket_connect("/ws/request-message") as websocket:
        second_message = websocket.receive_text()
        assert second_message.startswith("Request scoped message #")

    assert first_message != second_message


def test_websocket_concurrent_connections(client: TestClient) -> None:
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
