import inspect
from collections.abc import Callable, Iterator
from typing import Tuple, cast

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


@pytest.fixture(autouse=True)
def anydi_setup_container(
    request: pytest.FixtureRequest,
) -> Iterator[Container | None]:
    try:
        container = request.getfixturevalue("container")
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
    return not marker and not inject_all


@pytest.fixture
def _anydi_injected_parameter_iterator(
    request: pytest.FixtureRequest,
) -> Callable[[], Iterator[Tuple[str, inspect.Parameter]]]:
    def _iterator() -> Iterator[Tuple[str, inspect.Parameter]]:
        for name, parameter in inspect.signature(request.function).parameters.items():
            if (
                ((interface := parameter.annotation) is parameter.empty)
                or interface in _unresolved
                or name in request.node.funcargs
            ):
                continue
            yield name, interface

    return _iterator


_unresolved = []


@pytest.fixture(autouse=True)
def _anydi_inject(
    request: pytest.FixtureRequest,
    anydi_setup_container: Container,
    _anydi_should_inject: bool,
    _anydi_injected_parameter_iterator: Callable[
        [], Iterator[Tuple[str, inspect.Parameter]]
    ],
) -> None:
    """Inject dependencies into the test function."""
    if not _anydi_should_inject:
        return

    if inspect.iscoroutinefunction(request.function):
        # Skip if the test is a coroutine function
        return

    # Setup the container
    container = anydi_setup_container

    for argname, interface in _anydi_injected_parameter_iterator():
        try:
            # Release the instance if it was already resolved
            container.release(interface)
            # Resolve the instance
            instance = container.resolve(interface)
        except (LookupError, TypeError):
            _unresolved.append(interface)
            continue
        request.node.funcargs[argname] = instance


@pytest.fixture(autouse=True)
async def _anydi_ainject(
    request: pytest.FixtureRequest,
    anydi_setup_container: Container,
    _anydi_should_inject: bool,
    _anydi_injected_parameter_iterator: Callable[
        [], Iterator[Tuple[str, inspect.Parameter]]
    ],
) -> None:
    """Inject dependencies into the test function."""
    if not _anydi_should_inject:
        return

    # Setup the container
    container = anydi_setup_container

    for argname, interface in _anydi_injected_parameter_iterator():
        try:
            # Release the instance if it was already resolved
            container.release(interface)
            # Resolve the instance
            instance = await container.aresolve(interface)
        except (LookupError, TypeError):
            _unresolved.append(interface)
            continue
        request.node.funcargs[argname] = instance
