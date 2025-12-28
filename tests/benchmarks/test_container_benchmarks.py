"""Benchmarks for Container operations."""

import pytest
from pytest_codspeed import BenchmarkFixture

from anydi import Container, Inject, Provide


class SimpleService:
    """Simple service for benchmarking."""

    def __init__(self) -> None:
        self.value = "test"

    def get_value(self) -> str:
        return self.value


class DependentService:
    """Service with dependencies for benchmarking."""

    def __init__(self, simple: SimpleService) -> None:
        self.simple = simple

    def get_value(self) -> str:
        return self.simple.get_value()


@pytest.fixture
def container() -> Container:
    """Create a container for benchmarks."""
    return Container()


def test_container_creation(benchmark: BenchmarkFixture) -> None:
    """Benchmark container creation."""

    @benchmark
    def create_container() -> Container:
        return Container()


def test_provider_registration(benchmark: BenchmarkFixture, container: Container) -> None:
    """Benchmark provider registration."""

    @benchmark
    def register_provider() -> None:
        container.register(SimpleService, SimpleService, scope="transient")


def test_singleton_resolution(benchmark: BenchmarkFixture) -> None:
    """Benchmark singleton scope resolution."""
    container = Container()

    @container.provider(scope="singleton")
    def service() -> SimpleService:
        return SimpleService()

    @benchmark
    def resolve() -> SimpleService:
        return container.resolve(SimpleService)


def test_transient_resolution(benchmark: BenchmarkFixture) -> None:
    """Benchmark transient scope resolution."""
    container = Container()

    @container.provider(scope="transient")
    def service() -> SimpleService:
        return SimpleService()

    @benchmark
    def resolve() -> SimpleService:
        return container.resolve(SimpleService)


def test_dependency_injection(benchmark: BenchmarkFixture) -> None:
    """Benchmark dependency injection."""
    container = Container()

    @container.provider(scope="singleton")
    def simple_service() -> SimpleService:
        return SimpleService()

    @container.provider(scope="transient")
    def dependent_service(simple: Provide[SimpleService]) -> DependentService:
        return DependentService(simple)

    @benchmark
    def resolve() -> DependentService:
        return container.resolve(DependentService)


def test_inject_decorator(benchmark: BenchmarkFixture) -> None:
    """Benchmark @inject decorator."""
    container = Container()

    @container.provider(scope="singleton")
    def service() -> SimpleService:
        return SimpleService()

    @container.inject
    def function_with_injection(svc: SimpleService = Inject()) -> str:
        return svc.get_value()

    @benchmark
    def call_injected_function() -> str:
        return function_with_injection()


def test_nested_dependencies(benchmark: BenchmarkFixture) -> None:
    """Benchmark resolution with nested dependencies."""
    container = Container()

    class Level1:
        def __init__(self) -> None:
            self.value = "level1"

    class Level2:
        def __init__(self, level1: Level1) -> None:
            self.level1 = level1

    class Level3:
        def __init__(self, level2: Level2) -> None:
            self.level2 = level2

    @container.provider(scope="singleton")
    def level1() -> Level1:
        return Level1()

    @container.provider(scope="transient")
    def level2(l1: Provide[Level1]) -> Level2:
        return Level2(l1)

    @container.provider(scope="transient")
    def level3(l2: Provide[Level2]) -> Level3:
        return Level3(l2)

    @benchmark
    def resolve() -> Level3:
        return container.resolve(Level3)


def test_override_provider(benchmark: BenchmarkFixture) -> None:
    """Benchmark provider override."""
    container = Container()

    @container.provider(scope="singleton")
    def service() -> SimpleService:
        return SimpleService()

    mock_service = SimpleService()
    mock_service.value = "mocked"

    @benchmark
    def resolve_with_override() -> str:
        with container.override(SimpleService, mock_service):
            return container.resolve(SimpleService).get_value()
