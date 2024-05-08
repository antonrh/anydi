from django.test import AsyncClient, Client


def test_injected_setting(client: Client) -> None:
    response = client.get("/get-setting/")

    assert response.status_code == 200
    assert response.content == b"Hello, World!"


async def test_injected_setting_async(async_client: AsyncClient) -> None:
    response = await async_client.get("/get-setting-async/")

    assert response.status_code == 200
    assert response.content == b"Hello, World!"


def test_configure_dependency(client: Client) -> None:
    response = client.get("/get-configured-dependency/")

    assert response.status_code == 200
    assert response.content == b"This is configured string"


def test_request_scoped_dependency(client: Client) -> None:
    response = client.get("/get-request-scoped-dependency/")

    assert response.status_code == 200

    request_id = response.content

    response = client.get("/get-request-scoped-dependency/")

    next_request_id = response.content

    assert request_id != next_request_id


async def test_request_scoped_dependency_async(async_client: AsyncClient) -> None:
    response = await async_client.get("/get-request-scoped-dependency-async/")

    assert response.status_code == 200

    request_id = response.content

    response = await async_client.get("/get-request-scoped-dependency-async/")

    next_request_id = response.content

    assert request_id != next_request_id
