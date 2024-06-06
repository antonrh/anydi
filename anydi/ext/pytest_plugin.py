from __future__ import annotations

import inspect
from typing import Any, Callable, Iterator, cast

import pytest

from anydi import Container
from anydi._utils import get_typed_parameters


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "inject: mark test as needing dependency injection",
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addini(
        "anydi_inject_all",
        help="Inject all dependencies",
        type="bool",
        default=False,
    )


CONTAINER_FIXTURE_NAME = "container"


@pytest.fixture
def anydi_setup_container(
    request: pytest.FixtureRequest,
) -> Iterator[Container]:
    try:
        container = request.getfixturevalue(CONTAINER_FIXTURE_NAME)
    except pytest.FixtureLookupError as exc:
        exc.msg = (
            "`container` fixture is not found. Make sure to define it in your test "
            "module or override `anydi_setup_container` fixture."
        )
        raise exc

    yield container


@pytest.fixture
def _anydi_should_inject(request: pytest.FixtureRequest) -> bool:
    marker = request.node.get_closest_marker("inject")
    inject_all = cast(bool, request.config.getini("anydi_inject_all"))
    return marker is not None or inject_all


@pytest.fixture(scope="session")
def _anydi_unresolved() -> Iterator[list[Any]]:
    unresolved: list[Any] = []
    yield unresolved
    unresolved.clear()


@pytest.fixture
def _anydi_injected_parameter_iterator(
    request: pytest.FixtureRequest,
    _anydi_unresolved: list[str],
) -> Callable[[], Iterator[tuple[str, Any]]]:
    registered_fixtures = request.session._fixturemanager._arg2fixturedefs  # noqa

    def _iterator() -> Iterator[tuple[str, inspect.Parameter]]:
        for parameter in get_typed_parameters(request.function):
            interface = parameter.annotation
            if (
                interface is parameter.empty
                or interface in _anydi_unresolved
                or parameter.name in registered_fixtures
            ):
                continue
            yield parameter.name, interface

    return _iterator


@pytest.fixture(autouse=True)
def _anydi_inject(
    request: pytest.FixtureRequest,
    _anydi_should_inject: bool,
    _anydi_injected_parameter_iterator: Callable[[], Iterator[tuple[str, Any]]],
    _anydi_unresolved: list[str],
) -> None:
    """Inject dependencies into the test function."""

    if inspect.iscoroutinefunction(request.function) or not _anydi_should_inject:
        return

    # Setup the container
    container = cast(Container, request.getfixturevalue("anydi_setup_container"))

    for argname, interface in _anydi_injected_parameter_iterator():
        # Skip if the interface is not registered
        if container.strict and not container.is_registered(interface):
            continue

        try:
            request.node.funcargs[argname] = container.resolve(interface)
        except Exception:  # noqa
            _anydi_unresolved.append(interface)


@pytest.fixture(autouse=True)
async def _anydi_ainject(
    request: pytest.FixtureRequest,
    _anydi_should_inject: bool,
    _anydi_injected_parameter_iterator: Callable[[], Iterator[tuple[str, Any]]],
    _anydi_unresolved: list[str],
) -> None:
    """Inject dependencies into the test function."""
    if not inspect.iscoroutinefunction(request.function) or not _anydi_should_inject:
        return

    # Setup the container
    container = cast(Container, request.getfixturevalue("anydi_setup_container"))

    for argname, interface in _anydi_injected_parameter_iterator():
        # Skip if the interface is not registered
        if container.strict and not container.is_registered(interface):
            continue

        try:
            request.node.funcargs[argname] = await container.aresolve(interface)
        except Exception:  # noqa
            _anydi_unresolved.append(interface)
