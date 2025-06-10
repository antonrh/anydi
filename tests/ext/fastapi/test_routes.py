from unittest import mock

from starlette.testclient import TestClient

from anydi.testing import TestContainer

from tests.ext.fixtures import TEST_EMAIL, Mail, MailService, User, UserService


def test_send_mail(client: TestClient) -> None:
    message = "test"

    response = client.post("/send-mail", json={"message": message})

    assert response.status_code == 200
    assert response.json() == {
        "email": TEST_EMAIL,
        "message": message,
    }


def test_send_mail_mock_mail_service(
    client: TestClient, container: TestContainer
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


def test_send_mail_mock_user_service(
    client: TestClient, container: TestContainer
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


def test_annotated_mixed(client: TestClient) -> None:
    response = client.get("/annotated-mixed")

    assert response.status_code == 200
    assert response.json() == [
        "message1",
        "message1_a",
        "message1_a_b",
        "message2",
    ]
