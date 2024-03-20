import inspect
from typing import Any, Callable, Iterator, List, Tuple, cast

import pytest

from anydi import Container


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
def _anydi_unresolved() -> Iterator[List[Any]]:
    unresolved: List[Any] = []
    yield unresolved
    unresolved.clear()


@pytest.fixture
def _anydi_injected_parameter_iterator(
    request: pytest.FixtureRequest,
    _anydi_unresolved: List[str],
) -> Callable[[], Iterator[Tuple[str, Any]]]:
    def _iterator() -> Iterator[Tuple[str, inspect.Parameter]]:
        for name, parameter in inspect.signature(request.function).parameters.items():
            if (
                ((interface := parameter.annotation) is parameter.empty)
                or interface in _anydi_unresolved
                or name in request.node.funcargs
            ):
                continue
            yield name, interface

    return _iterator


@pytest.fixture(autouse=True)
def _anydi_inject(
    request: pytest.FixtureRequest,
    _anydi_should_inject: bool,
    _anydi_injected_parameter_iterator: Callable[[], Iterator[Tuple[str, Any]]],
    _anydi_unresolved: List[str],
) -> None:
    """Inject dependencies into the test function."""

    if inspect.iscoroutinefunction(request.function) or not _anydi_should_inject:
        return

    # Setup the container
    container = cast(Container, request.getfixturevalue("anydi_setup_container"))

    for argname, interface in _anydi_injected_parameter_iterator():
        try:
            # Release the instance if it was already resolved
            container.release(interface)
        except LookupError:
            pass
        try:
            # Resolve the instance
            instance = container.resolve(interface)
        except LookupError:
            _anydi_unresolved.append(interface)
            continue
        request.node.funcargs[argname] = instance


@pytest.fixture(autouse=True)
async def _anydi_ainject(
    request: pytest.FixtureRequest,
    _anydi_should_inject: bool,
    _anydi_injected_parameter_iterator: Callable[[], Iterator[Tuple[str, Any]]],
    _anydi_unresolved: List[str],
) -> None:
    """Inject dependencies into the test function."""
    if not inspect.iscoroutinefunction(request.function) or not _anydi_should_inject:
        return

    # Setup the container
    container = cast(Container, request.getfixturevalue("anydi_setup_container"))

    for argname, interface in _anydi_injected_parameter_iterator():
        try:
            # Release the instance if it was already resolved
            container.release(interface)
        except LookupError:
            pass
        try:
            # Resolve the instance
            instance = await container.aresolve(interface)
        except LookupError:
            _anydi_unresolved.append(interface)
            continue
        request.node.funcargs[argname] = instance
