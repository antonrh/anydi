from django.test import AsyncClient, Client


def test_say_hello(client: Client) -> None:
    response = client.get("/api/say-hello", data={"name": "World"})

    assert response.status_code == 200
    assert response.json() == "Hello, World!"


async def test_async_say_hello(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/say-hello-async", data={"name": "World"})

    assert response.status_code == 200
    assert response.json() == "Hello, World!"
