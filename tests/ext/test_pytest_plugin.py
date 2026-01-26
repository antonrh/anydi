from collections.abc import AsyncIterator, Iterator
from typing import Annotated, Any
from unittest import mock

import pytest

from anydi import Container, Inject, Provide
from anydi.ext import pytest_plugin


class Repository:
    """Repository for testing override scenarios."""

    def get(self, item_id: int) -> dict[str, Any] | None:
        return None


class Service:
    """Service with repository dependency for testing."""

    name = "service"

    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def get_item(self, item_id: int) -> dict[str, Any] | None:
        return self.repo.get(item_id)


class UnknownService:
    pass


@pytest.fixture(scope="session")
def container() -> Container:
    container = Container()
    container.register(Repository)
    container.register(Service)
    return container


def test_anydi_autoinject_default(request: pytest.FixtureRequest) -> None:
    assert request.config.getini("anydi_autoinject") is False


def test_anydi_inject_all_default(request: pytest.FixtureRequest) -> None:
    """Test deprecated option still works (for backward compatibility)."""
    assert request.config.getini("anydi_inject_all") is False


def test_no_container_setup(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Store original getini
    original_getini = request.config.getini

    # No config set
    def mock_getini(key: str):  # type: ignore[no-untyped-def]
        if key == "anydi_container":
            return None
        return original_getini(key)

    monkeypatch.setattr(request.config, "getini", mock_getini)

    with pytest.raises(pytest.FixtureLookupError) as exc_info:
        pytest_plugin._find_container(request)

    assert exc_info.value.msg is not None
    assert (
        "`container` fixture is not found and 'anydi_container' config is not set"
        in exc_info.value.msg
    )


@pytest.mark.inject
def test_inject_service(service: Service) -> None:
    assert isinstance(service, Service)


@pytest.mark.xfail
@pytest.mark.inject
def test_inject_unknown_service(unknown_service: UnknownService) -> None:
    pass


@pytest.mark.inject
async def test_ainject_service(service: Service) -> None:
    assert isinstance(service, Service)


@pytest.mark.xfail
@pytest.mark.inject
async def test_ainject_unknown_service(unknown_service: UnknownService) -> None:
    pass


@pytest.mark.xfail
@pytest.mark.inject
def test_inject_missing_type(service) -> None:  # type: ignore[no-untyped-def]
    pass


def test_get_container_from_config(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that container can be loaded from config (colon format)."""

    # Store original getini
    original_getini = request.config.getini

    # Set the config option
    def mock_getini(key: str):  # type: ignore[no-untyped-def]
        if key == "anydi_container":
            return "tests.test_container:_container_instance"
        return original_getini(key)

    monkeypatch.setattr(request.config, "getini", mock_getini)

    container = pytest_plugin._find_container(request)
    assert isinstance(container, Container)


def test_get_container_from_config_dot_format(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test container can be loaded from config (dot format, backward compatible)."""

    # Store original getini
    original_getini = request.config.getini

    # Set the config option
    def mock_getini(key: str) -> Any:
        if key == "anydi_container":
            return "tests.test_container._container_instance"
        return original_getini(key)

    monkeypatch.setattr(request.config, "getini", mock_getini)

    _container = pytest_plugin._find_container(request)
    assert isinstance(_container, Container)


def test_get_container_fixture_priority(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that fixture takes priority over config."""
    # Store original getini
    original_getini = request.config.getini

    # Set the config option to a different container
    def mock_getini(key: str) -> Any:
        if key == "anydi_container":
            return "tests.test_container:_container_factory"
        return original_getini(key)

    monkeypatch.setattr(request.config, "getini", mock_getini)

    # Should use the fixture, not the config
    _container = pytest_plugin._find_container(request)
    assert isinstance(_container, Container)


def test_get_container_no_fixture_no_config(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test error when neither fixture nor config is available."""
    # Store original getini
    original_getini = request.config.getini

    # No config set
    def mock_getini(key: str):  # type: ignore[no-untyped-def]
        if key == "anydi_container":
            return None
        return original_getini(key)

    monkeypatch.setattr(request.config, "getini", mock_getini)

    with pytest.raises(
        pytest.FixtureLookupError, match="container.*fixture is not found"
    ):
        pytest_plugin._find_container(request)


@pytest.fixture
def injected_fixture(service: Provide[Service]) -> str:
    return service.name


def test_inject_into_fixture(injected_fixture: str) -> None:
    assert injected_fixture == "service"


@pytest.fixture
def injected_generator_fixture(service: Provide[Service]) -> Iterator[str]:
    yield service.name  # noqa: PT022


def test_inject_into_generator_fixture(injected_generator_fixture: str) -> None:
    assert injected_generator_fixture == "service"


@pytest.fixture
async def injected_async_fixture(service: Provide[Service]) -> str:
    return service.name


async def test_inject_into_async_fixture(injected_async_fixture: str) -> None:
    assert injected_async_fixture == "service"


@pytest.fixture
async def injected_async_generator_fixture(
    service: Provide[Service],
) -> AsyncIterator[str]:
    yield service.name  # noqa: PT022


async def test_inject_into_async_generator_fixture(
    injected_async_generator_fixture: str,
) -> None:
    assert injected_async_generator_fixture == "service"


def test_container_test_mode_enabled(container: Container) -> None:
    """Test that container is in test mode when enable_test_mode is called."""
    assert container._test_mode is True


@pytest.mark.inject
def test_override_works_for_injected_service(
    container: Container, service: Service
) -> None:
    """Test that override works for already-resolved injected services."""

    # Verify service works with original repository
    assert service.get_item(100) is None

    # Create mock repository
    repo_mock = mock.MagicMock(spec=Repository)
    repo_mock.get.return_value = {"id": 100, "name": "mocked"}

    # Override should work for the already-injected service
    with container.override(Repository, instance=repo_mock):
        item = service.get_item(100)

        assert item is not None
        assert item["id"] == 100
        assert item["name"] == "mocked"

    # After override context, original behavior is restored
    assert service.get_item(100) is None


def test_explicit_provide_in_test(service: Provide[Service]) -> None:
    """Test explicit injection via Provide[T] in test functions."""
    assert isinstance(service, Service)
    assert service.name == "service"


async def test_explicit_provide_in_async_test(service: Provide[Service]) -> None:
    """Test explicit injection via Provide[T] in async test functions."""
    assert isinstance(service, Service)
    assert service.name == "service"


def test_explicit_annotated_inject_in_test(
    service: Annotated[Service, Inject()],
) -> None:
    """Test explicit injection via Annotated[T, Inject()] in test functions."""
    assert isinstance(service, Service)
    assert service.name == "service"


async def test_explicit_annotated_inject_in_async_test(
    service: Annotated[Service, Inject()],
) -> None:
    """Test explicit injection via Annotated[T, Inject()] in async test functions."""
    assert isinstance(service, Service)
    assert service.name == "service"


@pytest.fixture
def fixture_with_provide(repo: Provide[Repository]) -> Service:
    """Fixture using Provide[T] for explicit injection."""
    return Service(repo)


def test_fixture_with_provide(fixture_with_provide: Service) -> None:
    """Test fixture with Provide[T] explicit injection."""
    assert isinstance(fixture_with_provide, Service)
    assert isinstance(fixture_with_provide.repo, Repository)


@pytest.fixture
def fixture_with_annotated_inject(repo: Annotated[Repository, Inject()]) -> Service:
    """Fixture using Annotated[T, Inject()] for explicit injection."""
    return Service(repo)


def test_fixture_with_annotated_inject(fixture_with_annotated_inject: Service) -> None:
    """Test fixture with Annotated[T, Inject()] explicit injection."""
    assert isinstance(fixture_with_annotated_inject, Service)
    assert isinstance(fixture_with_annotated_inject.repo, Repository)


@pytest.fixture
async def async_fixture_with_provide(repo: Provide[Repository]) -> Service:
    """Async fixture using Provide[T] for explicit injection."""
    return Service(repo)


async def test_async_fixture_with_provide(
    async_fixture_with_provide: Service,
) -> None:
    """Test async fixture with Provide[T] explicit injection."""
    assert isinstance(async_fixture_with_provide, Service)
    assert isinstance(async_fixture_with_provide.repo, Repository)


@pytest.fixture
async def async_generator_fixture_with_provide(
    repo: Provide[Repository],
) -> AsyncIterator[Service]:
    """Async generator fixture using Provide[T] for explicit injection."""
    yield Service(repo)
    assert True


async def test_async_generator_fixture_with_provide(
    async_generator_fixture_with_provide: Service,
) -> None:
    """Test async generator fixture with Provide[T] explicit injection."""
    assert isinstance(async_generator_fixture_with_provide, Service)
    assert isinstance(async_generator_fixture_with_provide.repo, Repository)


@pytest.fixture
def settings_fixture() -> dict[str, str]:
    """Regular pytest fixture."""
    return {"env": "test", "debug": "true"}


@pytest.fixture
def fixture_with_mixed_params(
    repo: Provide[Repository],
    settings_fixture: dict[str, str],
) -> tuple[Service, dict[str, str]]:
    """Fixture mixing DI injection (Provide) with regular pytest fixtures."""
    return Service(repo), settings_fixture


def test_fixture_with_mixed_params(
    fixture_with_mixed_params: tuple[Service, dict[str, str]],
) -> None:
    """Test fixture that mixes DI and regular pytest fixtures."""
    service, settings = fixture_with_mixed_params
    assert isinstance(service, Service)
    assert isinstance(service.repo, Repository)
    assert settings == {"env": "test", "debug": "true"}


def test_mixed_params_in_test(
    service: Provide[Service],
    settings_fixture: dict[str, str],
) -> None:
    """Test mixing DI injection with regular pytest fixtures in test function."""
    assert isinstance(service, Service)
    assert settings_fixture == {"env": "test", "debug": "true"}


def test_explicit_injection_priority(
    repo: Provide[Repository],  # Explicit - should be injected
    container: Container,  # Regular fixture - should use fixture
) -> None:
    """Test that explicit markers take priority and coexist with fixtures."""
    assert isinstance(repo, Repository)
    assert isinstance(container, Container)


def test_anydi_fixture_inject_enabled_exists(request: pytest.FixtureRequest) -> None:
    """Test anydi_fixture_inject_enabled config option exists."""
    # Note: Default is False, but we set it to True in pyproject.toml for tests
    value = request.config.getini("anydi_fixture_inject_enabled")
    assert isinstance(value, bool)


class NonResolvableType:
    """Type that is NOT registered in the container."""

    value: str

    def __init__(self, value: str) -> None:
        self.value = value


@pytest.fixture
def non_resolvable_fixture() -> NonResolvableType:
    """Fixture returning a type not in container."""
    return NonResolvableType("test_value")


@pytest.fixture
def fixture_depending_on_non_resolvable(
    non_resolvable_fixture: NonResolvableType,
) -> str:
    """Fixture with type-annotated param that's a pytest fixture, not from container."""
    return non_resolvable_fixture.value


def test_fixture_with_non_resolvable_dependency(
    fixture_depending_on_non_resolvable: str,
) -> None:
    """Test that fixtures with non-resolvable deps work correctly."""
    assert fixture_depending_on_non_resolvable == "test_value"
