from __future__ import annotations

import importlib.util
import inspect
import logging
import warnings
from typing import Annotated, Any, cast, get_args, get_origin

import pytest
from anyio.pytest_plugin import extract_backend_and_options, get_runner
from typing_extensions import get_annotations

from anydi import Container, import_container
from anydi._marker import is_marker

logger = logging.getLogger(__name__)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addini(
        "anydi_container",
        help=(
            "Path to container instance or factory "
            "(e.g., 'myapp.container:container' or 'myapp.container.container')"
        ),
        type="string",
        default=None,
    )
    parser.addini(
        "anydi_autoinject",
        help="Automatically inject dependencies into all test functions",
        type="bool",
        default=True,
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "inject: mark test as needing dependency injection (deprecated)",
    )


@pytest.fixture(scope="session")
def container(request: pytest.FixtureRequest) -> Container:
    """Container fixture with testing mode enabled."""
    container = _find_container(request)
    container.enable_test_mode()
    return container


@pytest.fixture(autouse=True)
def _anydi_inject(request: pytest.FixtureRequest) -> None:
    """Inject dependencies into sync test functions."""
    if inspect.iscoroutinefunction(request.function):
        return

    parameters, uses_deprecated = _get_injectable_params(request)
    if not parameters:
        return

    container = cast(Container, request.getfixturevalue("container"))
    container.enable_test_mode()

    resolvable = [
        (name, tp) for name, tp in parameters if container.has_provider_for(tp)
    ]
    if not resolvable:
        return

    if uses_deprecated:
        _warn_deprecated_marker(request.node.name)

    for name, dependency_type in resolvable:
        try:
            request.node.funcargs[name] = container.resolve(dependency_type)
        except Exception:  # pragma: no cover
            logger.warning("Failed to resolve '%s' for %s", name, request.node.nodeid)


@pytest.fixture(autouse=True)
def _anydi_ainject(request: pytest.FixtureRequest) -> None:
    """Inject dependencies into async test functions."""
    if not inspect.iscoroutinefunction(
        request.function
    ) and not inspect.isasyncgenfunction(request.function):
        return

    parameters, uses_deprecated = _get_injectable_params(request)
    if not parameters:
        return

    if "anyio_backend" not in request.fixturenames:
        pytest.fail(
            "To run async test functions with `anyio`, "
            "please configure the `anyio` pytest plugin.\n"
            "See: https://anyio.readthedocs.io/en/stable/testing.html",
            pytrace=False,
        )

    container = cast(Container, request.getfixturevalue("container"))
    container.enable_test_mode()

    resolvable = [
        (name, tp) for name, tp in parameters if container.has_provider_for(tp)
    ]
    if not resolvable:
        return

    if uses_deprecated:
        _warn_deprecated_marker(request.node.name)

    async def _resolve() -> None:
        for name, tp in resolvable:
            try:
                request.node.funcargs[name] = await container.aresolve(tp)
            except Exception:  # pragma: no cover
                logger.warning(
                    "Failed to resolve '%s' for %s", name, request.node.nodeid
                )

    anyio_backend = request.getfixturevalue("anyio_backend")
    backend_name, backend_options = extract_backend_and_options(anyio_backend)

    with get_runner(backend_name, backend_options) as runner:
        runner.run_fixture(_resolve, {})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_injectable_params(
    request: pytest.FixtureRequest,
) -> tuple[list[tuple[str, Any]], bool]:
    """Get injectable parameters for a test function.

    Returns (parameters, uses_deprecated_marker) tuple.
    """
    fixture_names = set(request.node._fixtureinfo.initialnames) - set(
        request.node._fixtureinfo.name2fixturedefs.keys()
    )

    marker = request.node.get_closest_marker("inject")
    autoinject = cast(bool, request.config.getini("anydi_autoinject"))

    has_any_explicit = False
    explicit_params: list[tuple[str, Any]] = []
    all_params: list[tuple[str, Any]] = []

    annotations = get_annotations(request.function, eval_str=True)

    for name, annotation in annotations.items():
        if name in ("request", "return"):
            continue

        tp, is_explicit = _extract_type(annotation)

        if is_explicit:
            has_any_explicit = True
            explicit_params.append((name, tp))
        elif name in fixture_names:
            all_params.append((name, tp))

    # Priority: explicit markers > deprecated @pytest.mark.inject > autoinject
    if has_any_explicit:
        return explicit_params, False
    if marker is not None:
        return all_params, True
    if autoinject:
        return all_params, False
    return [], False


def _extract_type(annotation: Any) -> tuple[Any, bool]:
    """Extract the actual type and whether it has an explicit injection marker.

    Handles Provide[T] and Annotated[T, Inject()].
    Returns (unwrapped_type, is_explicit).
    """
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        for arg in args[1:]:
            if is_marker(arg):
                return args[0], True
    return annotation, False


def _find_container(request: pytest.FixtureRequest) -> Container:
    """Find container from config or auto-detection."""
    container_path = cast(str | None, request.config.getini("anydi_container"))
    if container_path:
        try:
            return import_container(container_path)
        except ImportError as exc:
            raise RuntimeError(
                f"Failed to load container from config "
                f"'anydi_container={container_path}': {exc}"
            ) from exc

    pluginmanager = request.config.pluginmanager
    if pluginmanager.hasplugin("django") and importlib.util.find_spec("anydi_django"):
        return import_container("anydi_django.container")

    raise pytest.FixtureLookupError(
        None,
        request,
        "`container` fixture is not found and 'anydi_container' config is not set. "
        "Either define a `container` fixture in your test module "
        "or set 'anydi_container' in pytest.ini.",
    )


def _warn_deprecated_marker(test_name: str) -> None:
    warnings.warn(
        f"Using @pytest.mark.inject on test '{test_name}' is "
        "deprecated. Use Provide[T] or Annotated[T, Inject()] instead.",
        DeprecationWarning,
        stacklevel=4,
    )
