from __future__ import annotations

import inspect
import logging
from collections.abc import Iterator
from typing import Any, Callable, cast

import pytest
from anyio.pytest_plugin import extract_backend_and_options, get_runner

from anydi import Container
from anydi._typing import get_typed_parameters

logger = logging.getLogger(__name__)


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
def anydi_setup_container(request: pytest.FixtureRequest) -> Container:
    try:
        return cast(Container, request.getfixturevalue(CONTAINER_FIXTURE_NAME))
    except pytest.FixtureLookupError as exc:
        exc.msg = (
            "`container` fixture is not found. Make sure to define it in your test "
            "module or override `anydi_setup_container` fixture."
        )
        raise exc


@pytest.fixture
def _anydi_should_inject(request: pytest.FixtureRequest) -> bool:
    marker = request.node.get_closest_marker("inject")
    inject_all = cast(bool, request.config.getini("anydi_inject_all"))
    return marker is not None or inject_all


@pytest.fixture
def _anydi_injected_parameter_iterator(
    request: pytest.FixtureRequest,
) -> Callable[[], Iterator[tuple[str, Any]]]:
    fixturenames = set(request.node._fixtureinfo.initialnames) - set(
        request.node._fixtureinfo.name2fixturedefs.keys()
    )

    def _iterator() -> Iterator[tuple[str, inspect.Parameter]]:
        for parameter in get_typed_parameters(request.function):
            interface = parameter.annotation
            if (
                interface is inspect.Parameter.empty
                or parameter.name not in fixturenames
            ):
                continue
            yield parameter.name, interface

    return _iterator


@pytest.fixture(autouse=True)
def _anydi_inject(
    request: pytest.FixtureRequest,
    _anydi_should_inject: bool,
    _anydi_injected_parameter_iterator: Callable[[], Iterator[tuple[str, Any]]],
) -> None:
    """Inject dependencies into the test function."""

    if inspect.iscoroutinefunction(request.function) or not _anydi_should_inject:
        return

    # Setup the container
    container = cast(Container, request.getfixturevalue("anydi_setup_container"))

    for argname, interface in _anydi_injected_parameter_iterator():
        # Skip if the interface has no provider
        if not container.has_provider_for(interface):
            continue

        try:
            request.node.funcargs[argname] = container.resolve(interface)
        except Exception as exc:
            logger.warning(
                f"Failed to resolve dependency for argument '{argname}'.", exc_info=exc
            )


@pytest.fixture(autouse=True)
def _anydi_ainject(
    request: pytest.FixtureRequest,
    _anydi_should_inject: bool,
    _anydi_injected_parameter_iterator: Callable[[], Iterator[tuple[str, Any]]],
) -> None:
    """Inject dependencies into the test function."""
    if (
        not inspect.iscoroutinefunction(request.function)
        and not inspect.isasyncgenfunction(request.function)
        or not _anydi_should_inject
    ):
        return

    # Skip if the anyio backend is not available
    if "anyio_backend" not in request.fixturenames:
        msg = (
            "To run async test functions with `anyio`, "
            "please configure the `anyio` pytest plugin.\n"
            "See: https://anyio.readthedocs.io/en/stable/testing.html"
        )
        pytest.fail(msg, pytrace=False)

    async def _awrapper() -> None:
        # Setup the container
        container = cast(Container, request.getfixturevalue("anydi_setup_container"))

        for argname, interface in _anydi_injected_parameter_iterator():
            # Skip if the interface has no provider
            if not container.has_provider_for(interface):
                continue

            try:
                request.node.funcargs[argname] = await container.aresolve(interface)
            except Exception as exc:
                logger.warning(
                    f"Failed to resolve dependency for argument '{argname}'.",
                    exc_info=exc,
                )

    anyio_backend = request.getfixturevalue("anyio_backend")
    backend_name, backend_options = extract_backend_and_options(anyio_backend)

    with get_runner(backend_name, backend_options) as runner:
        runner.run_fixture(_awrapper, {})
