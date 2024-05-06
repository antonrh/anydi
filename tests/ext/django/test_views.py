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
