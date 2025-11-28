from typing import Any

import pytest

from anydi import Container
from anydi.ext import pytest_plugin


class Service:
    pass


class UnknownService:
    pass


@pytest.fixture(scope="module")
def container() -> Container:
    container = Container()
    container.register(Service, lambda: Service(), scope="singleton")
    return container


def test_anydi_autoinject_default(request: pytest.FixtureRequest) -> None:
    assert request.config.getini("anydi_autoinject") is False


def test_anydi_inject_all_default(request: pytest.FixtureRequest) -> None:
    """Test deprecated option still works (for backward compatibility)."""
    assert request.config.getini("anydi_inject_all") is False


def test_no_container_setup(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pytest_plugin, "CONTAINER_FIXTURE_NAME", "container1")

    # Store original getini
    original_getini = request.config.getini

    # No config set
    def mock_getini(key: str):  # type: ignore[no-untyped-def]
        if key == "anydi_container":
            return None
        return original_getini(key)

    monkeypatch.setattr(request.config, "getini", mock_getini)

    with pytest.raises(pytest.FixtureLookupError) as exc_info:
        request.getfixturevalue("anydi_setup_container")

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


def test_anydi_setup_container_from_config(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that container can be loaded from config (colon format)."""
    # Remove the container fixture
    monkeypatch.setattr(
        pytest_plugin,
        "CONTAINER_FIXTURE_NAME",
        "nonexistent_fixture",
    )

    # Store original getini
    original_getini = request.config.getini

    # Set the config option
    def mock_getini(key: str):  # type: ignore[no-untyped-def]
        if key == "anydi_container":
            return "tests.test_container:_container_instance"
        return original_getini(key)

    monkeypatch.setattr(request.config, "getini", mock_getini)

    container = request.getfixturevalue("anydi_setup_container")
    assert isinstance(container, Container)


def test_anydi_setup_container_from_config_dot_format(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test container can be loaded from config (dot format, backward compatible)."""
    # Remove the container fixture
    monkeypatch.setattr(
        pytest_plugin,
        "CONTAINER_FIXTURE_NAME",
        "nonexistent_fixture",
    )

    # Store original getini
    original_getini = request.config.getini

    # Set the config option
    def mock_getini(key: str) -> Any:
        if key == "anydi_container":
            return "tests.test_container._container_instance"
        return original_getini(key)

    monkeypatch.setattr(request.config, "getini", mock_getini)

    _container = request.getfixturevalue("anydi_setup_container")
    assert isinstance(_container, Container)


def test_anydi_setup_container_fixture_priority(
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
    _container = request.getfixturevalue("anydi_setup_container")
    assert isinstance(_container, Container)


def test_anydi_setup_container_no_fixture_no_config(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test error when neither fixture nor config is available."""
    # Remove the container fixture
    monkeypatch.setattr(pytest_plugin, "CONTAINER_FIXTURE_NAME", "nonexistent_fixture")

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
        request.getfixturevalue("anydi_setup_container")
