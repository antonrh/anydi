"""Benchmarks for async Container operations."""

from collections.abc import AsyncIterator

import pytest
from pytest_codspeed import BenchmarkFixture

from anydi import Container, Provide


class AsyncService:
    """Async service for benchmarking."""

    def __init__(self) -> None:
        self.value = "test"

    async def get_value(self) -> str:
        return self.value


class AsyncDependentService:
    """Service with async dependencies for benchmarking."""

    def __init__(self, async_svc: AsyncService) -> None:
        self.async_svc = async_svc

    async def get_value(self) -> str:
        return await self.async_svc.get_value()


@pytest.fixture
def container() -> Container:
    """Create a container for benchmarks."""
    return Container()


def test_async_provider_resolution(benchmark: BenchmarkFixture) -> None:
    """Benchmark async provider resolution."""
    container = Container()

    @container.provider(scope="singleton")
    async def async_service() -> AsyncService:
        return AsyncService()

    @benchmark
    async def resolve() -> AsyncService:
        return await container.aresolve(AsyncService)


def test_async_dependency_injection(benchmark: BenchmarkFixture) -> None:
    """Benchmark async dependency injection."""
    container = Container()

    @container.provider(scope="singleton")
    async def async_service() -> AsyncService:
        return AsyncService()

    @container.provider(scope="transient")
    async def dependent_service(
        async_svc: Provide[AsyncService],
    ) -> AsyncDependentService:
        return AsyncDependentService(async_svc)

    @benchmark
    async defresolve() -> AsyncDependentService:
        return await container.aresolve(AsyncDependentService)


def test_async_generator_provider(benchmark: BenchmarkFixture) -> None:
    """Benchmark async generator provider."""
    container = Container()

    @container.provider(scope="request")
    async def resource_provider() -> AsyncIterator[AsyncService]:
        service = AsyncService()
        yield service

    @benchmark
    async def resolve() -> AsyncService:
        async with container.arequest_context():
            return await container.aresolve(AsyncService)


def test_async_inject_decorator(benchmark: BenchmarkFixture) -> None:
    """Benchmark @inject decorator with async functions."""
    container = Container()

    @container.provider(scope="singleton")
    async def service() -> AsyncService:
        return AsyncService()

    @container.inject
    async def async_function(svc: Provide[AsyncService]) -> str:
        return await svc.get_value()

    @benchmark
    async def call_injected_function() -> str:
        return await async_function()
