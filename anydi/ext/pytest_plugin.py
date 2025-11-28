from __future__ import annotations

import importlib.util
import inspect
import logging
from collections.abc import Callable, Iterator
from typing import Any, cast

import pytest
from anyio.pytest_plugin import extract_backend_and_options, get_runner
from typing_extensions import get_annotations

from anydi import Container, import_container

logger = logging.getLogger(__name__)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "inject: mark test as needing dependency injection",
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addini(
        "anydi_autoinject",
        help="Automatically inject dependencies into all test functions",
        type="bool",
        default=False,
    )
    parser.addini(
        "anydi_inject_all",
        help="Deprecated: use 'anydi_autoinject' instead",
        type="bool",
        default=False,
    )
    parser.addini(
        "anydi_container",
        help=(
            "Path to container instance or factory "
            "(e.g., 'myapp.container:container' or 'myapp.container.container')"
        ),
        type="string",
        default=None,
    )


@pytest.fixture(scope="session")
def container(request: pytest.FixtureRequest) -> Container:
    """Container fixture."""
    return _find_container(request)


@pytest.fixture
def _anydi_should_inject(request: pytest.FixtureRequest) -> bool:
    marker = request.node.get_closest_marker("inject")

    # Check new config option first
    autoinject = cast(bool, request.config.getini("anydi_autoinject"))

    # Check deprecated option for backward compatibility
    inject_all = cast(bool, request.config.getini("anydi_inject_all"))
    if inject_all:
        logger.warning(
            "Configuration option 'anydi_inject_all' is deprecated. "
            "Please use 'anydi_autoinject' instead."
        )

    return marker is not None or autoinject or inject_all


@pytest.fixture
def _anydi_injected_parameter_iterator(
    request: pytest.FixtureRequest,
) -> Callable[[], Iterator[tuple[str, Any]]]:
    fixturenames = set(request.node._fixtureinfo.initialnames) - set(
        request.node._fixtureinfo.name2fixturedefs.keys()
    )

    def _iterator() -> Iterator[tuple[str, inspect.Parameter]]:
        for name, annotation in get_annotations(
            request.function, eval_str=True
        ).items():
            if name == "return":
                continue
            if name not in fixturenames:
                continue
            yield name, annotation

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

    container = cast(Container, request.getfixturevalue("container"))

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

    container = cast(Container, request.getfixturevalue("container"))

    async def _awrapper() -> None:
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


def _find_container(request: pytest.FixtureRequest) -> Container:
    """Find container."""

    # Look for 'anydi_container' defined in pytest.ini (highest priority)
    container_path = cast(str | None, request.config.getini("anydi_container"))
    if container_path:
        try:
            return import_container(container_path)
        except ImportError as exc:
            raise RuntimeError(
                f"Failed to load container from config "
                f"'anydi_container={container_path}': {exc}"
            ) from exc

    # Detect pytest-django + anydi_django availability
    pluginmanager = request.config.pluginmanager
    if pluginmanager.hasplugin("django") and importlib.util.find_spec("anydi_django"):
        return import_container("anydi_django.container")

    # Neither fixture nor config found
    raise pytest.FixtureLookupError(
        None,
        request,
        "`container` fixture is not found and 'anydi_container' config is not set. "
        "Either define a `container` fixture in your test module "
        "or set 'anydi_container' in pytest.ini.",
    )
