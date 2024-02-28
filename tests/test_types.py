from typing import AsyncIterator, Iterator

from anydi import Provider

from tests.fixtures import Service


def test_provider_function_type() -> None:
    provider = Provider(obj=lambda: "test", scope="transient")

    assert provider.is_function
    assert not provider.is_class
    assert not provider.is_generator
    assert not provider.is_async_generator


def test_provider_function_class() -> None:
    provider = Provider(obj=Service, scope="transient")

    assert not provider.is_function
    assert provider.is_class
    assert not provider.is_generator
    assert not provider.is_async_generator


def test_provider_function_resource() -> None:
    def resource() -> Iterator[str]:
        yield "test"

    provider = Provider(obj=resource, scope="transient")

    assert not provider.is_function
    assert not provider.is_class
    assert provider.is_generator
    assert not provider.is_async_generator


def test_provider_function_async_resource() -> None:
    async def resource() -> AsyncIterator[str]:
        yield "test"

    provider = Provider(obj=resource, scope="transient")

    assert not provider.is_function
    assert not provider.is_class
    assert not provider.is_generator
    assert provider.is_async_generator


def test_provider_name() -> None:
    def obj() -> str:
        return "test"

    provider = Provider(obj=obj, scope="transient")

    assert (
        provider.name
        == str(provider)
        == "tests.test_types.test_provider_name.<locals>.obj"
    )
