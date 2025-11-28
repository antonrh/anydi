from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest

from anydi import Container
from anydi.ext import pytest_plugin


class Service:
    name = "service"


class UnknownService:
    pass


@pytest.fixture(scope="session")
def container() -> Container:
    container = Container()
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
@pytest.mark.inject
def injected_fixture(service: Service) -> str:
    return service.name


def test_inject_into_fixture(injected_fixture: str) -> None:
    assert injected_fixture == "service"


@pytest.fixture
@pytest.mark.inject
def injected_generator_fixture(service: Service) -> Iterator[str]:
    yield service.name  # noqa: PT022


def test_inject_into_generator_fixture(injected_generator_fixture: str) -> None:
    assert injected_generator_fixture == "service"


@pytest.fixture
@pytest.mark.inject
async def injected_async_fixture(service: Service) -> str:
    return service.name


async def test_inject_into_async_fixture(injected_async_fixture: str) -> None:
    assert injected_async_fixture == "service"


@pytest.fixture
@pytest.mark.inject
async def injected_async_generator_fixture(service: Service) -> AsyncIterator[str]:
    yield service.name  # noqa: PT022


async def test_inject_into_async_generator_fixture(
    injected_async_generator_fixture: str,
) -> None:
    assert injected_async_generator_fixture == "service"
