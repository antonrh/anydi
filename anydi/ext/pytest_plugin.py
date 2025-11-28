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

# Storage for fixtures with inject markers
_INJECTED_FIXTURES: dict[str, dict[str, Any]] = {}


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
    parser.addini(
        "anydi_inject_fixtures",
        help=(
            "Enable dependency injection into fixtures marked with @pytest.mark.inject"
        ),
        type="bool",
        default=True,
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "inject: mark test as needing dependency injection",
    )

    # Enable fixture injection if configured
    inject_fixtures_enabled = cast(bool, config.getini("anydi_inject_fixtures"))
    if inject_fixtures_enabled:
        _patch_pytest_fixtures()
        logger.debug("Fixture injection enabled via anydi_inject_fixtures config")


@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(
    fixturedef: pytest.FixtureDef[Any], request: pytest.FixtureRequest,
) -> Iterator[None]:
    """Inject dependencies into fixtures marked with @pytest.mark.inject."""
    # Check if this fixture has injection metadata
    fixture_name = fixturedef.argname
    if fixture_name not in _INJECTED_FIXTURES:
        yield
        return

    # Get the metadata
    fixture_info = _INJECTED_FIXTURES[fixture_name]
    original_func = fixture_info["func"]
    injected_params = fixture_info["injected_params"]
    annotations = fixture_info["annotations"]

    # Get the container
    try:
        container = cast(Container, request.getfixturevalue("container"))
    except pytest.FixtureLookupError:
        yield
        return

    # Prepare injected arguments
    injected_kwargs: dict[str, Any] = {}
    for param_name in injected_params:
        annotation = annotations.get(param_name)
        if annotation is None:
            continue

        # Try to resolve from container
        if container.has_provider_for(annotation):
            try:
                injected_kwargs[param_name] = container.resolve(annotation)
                logger.debug(
                    f"Resolved {param_name}={annotation} for fixture {fixture_name}"
                )
            except Exception as exc:
                logger.warning(
                    f"Failed to resolve dependency for fixture "
                    f"parameter '{param_name}'.",
                    exc_info=exc,
                )

    if not injected_kwargs:
        yield
        return

    def _prepare_call_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
        combined_kwargs = dict(kwargs)
        combined_kwargs.update(injected_kwargs)
        return combined_kwargs

    def _ensure_anyio_backend() -> tuple[str, dict[str, Any]]:
        try:
            backend = request.getfixturevalue("anyio_backend")
        except pytest.FixtureLookupError as exc:  # pragma: no cover - defensive
            msg = (
                "To run async fixtures with AnyDI, please configure the `anyio` pytest "
                "plugin (provide the `anyio_backend` fixture)."
            )
            pytest.fail(msg, pytrace=False)
            raise RuntimeError from exc  # Unreachable but satisfies type checkers

        return extract_backend_and_options(backend)

    # Replace the fixture function with one that mirrors the original's type and
    # injects dependencies before delegating to the user-defined function.
    original_fixture_func = fixturedef.func

    if inspect.isasyncgenfunction(original_func):

        def asyncgen_wrapper(*args: Any, **kwargs: Any) -> Iterator[Any]:
            backend_name, backend_options = _ensure_anyio_backend()
            call_kwargs = _prepare_call_kwargs(kwargs)

            with get_runner(backend_name, backend_options) as runner:
                yield from runner.run_asyncgen_fixture(original_func, call_kwargs)

        fixturedef.func = asyncgen_wrapper  # type: ignore[misc]
    elif inspect.iscoroutinefunction(original_func):

        def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            backend_name, backend_options = _ensure_anyio_backend()
            call_kwargs = _prepare_call_kwargs(kwargs)

            with get_runner(backend_name, backend_options) as runner:
                return runner.run_fixture(original_func, call_kwargs)

        fixturedef.func = async_wrapper  # type: ignore[misc]
    elif inspect.isgeneratorfunction(original_func):

        def generator_wrapper(*args: Any, **kwargs: Any) -> Iterator[Any]:
            call_kwargs = _prepare_call_kwargs(kwargs)
            yield from original_func(**call_kwargs)

        fixturedef.func = generator_wrapper  # type: ignore[misc]
    else:

        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            call_kwargs = _prepare_call_kwargs(kwargs)
            return original_func(**call_kwargs)

        fixturedef.func = sync_wrapper  # type: ignore[misc]

    # Let pytest execute the modified fixture
    yield

    # Restore the original function
    fixturedef.func = original_fixture_func  # type: ignore[misc]


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


def _patch_pytest_fixtures() -> None:  # noqa: C901
    """Patch pytest.fixture decorator to intercept fixtures with inject markers."""
    from _pytest.fixtures import fixture as original_fixture_decorator

    def patched_fixture(*args: Any, **kwargs: Any) -> Any:  # noqa: C901
        """Patched fixture decorator that handles inject markers."""

        # Handle both @pytest.fixture and @pytest.fixture() usage
        if len(args) == 1 and callable(args[0]) and not kwargs:
            # @pytest.fixture without parentheses
            func = args[0]

            # Check if this fixture has inject marker
            has_inject_marker = False
            if hasattr(func, "pytestmark"):
                markers = getattr(func, "pytestmark", [])
                if not isinstance(markers, list):
                    markers = [markers]

                has_inject_marker = any(
                    marker.name == "inject"
                    for marker in markers
                    if hasattr(marker, "name")
                )

            if has_inject_marker:
                # Get annotations and signature
                annotations = get_annotations(func, eval_str=True)
                sig = inspect.signature(func)

                injected_params = [
                    param_name
                    for param_name in sig.parameters.keys()
                    if param_name != "request" and param_name in annotations
                ]

                if injected_params:
                    # Create a wrapper function with no parameters (except request)
                    # This ensures pytest doesn't try to resolve the injected
                    # params as fixtures
                    request_param = sig.parameters.get("request")

                    if request_param:

                        def wrapper_with_request(request: Any) -> Any:
                            # Return the original func, we'll handle injection later
                            return func

                        wrapper_func = wrapper_with_request
                        wrapper_func.__name__ = func.__name__
                        wrapper_func.__annotations__ = {}  # Clear annotations
                    else:

                        def wrapper_no_request() -> Any:
                            return func

                        wrapper_func = wrapper_no_request
                        wrapper_func.__name__ = func.__name__
                        wrapper_func.__annotations__ = {}

                    # Store metadata
                    fixture_name = func.__name__
                    _INJECTED_FIXTURES[fixture_name] = {
                        "func": func,
                        "injected_params": injected_params,
                        "annotations": annotations,
                    }
                    logger.debug(
                        f"Registered injectable fixture '{fixture_name}' "
                        f"with params: {injected_params}"
                    )

                    # Call original decorator with the wrapper
                    result = original_fixture_decorator(wrapper_func)
                    # Store original func on the result
                    result._anydi_original_func = func  # type: ignore[attr-defined]
                    result._anydi_injected_params = injected_params  # type: ignore[attr-defined]
                    result._anydi_annotations = annotations  # type: ignore[attr-defined]
                    return result

            # No inject marker - proceed normally
            result = original_fixture_decorator(func)
            return result
        else:
            # @pytest.fixture() with parentheses - return decorator
            def decorator(func: Callable[..., Any]) -> Any:
                # Check if this fixture has inject marker
                has_inject_marker = False
                if hasattr(func, "pytestmark"):
                    markers = getattr(func, "pytestmark", [])
                    if not isinstance(markers, list):
                        markers = [markers]

                    has_inject_marker = any(
                        marker.name == "inject"
                        for marker in markers
                        if hasattr(marker, "name")
                    )

                if has_inject_marker:
                    # Get annotations and signature
                    annotations = get_annotations(func, eval_str=True)
                    sig = inspect.signature(func)

                    injected_params = [
                        param_name
                        for param_name in sig.parameters.keys()
                        if param_name != "request" and param_name in annotations
                    ]

                    if injected_params:
                        # Create a wrapper function with no parameters (except request)
                        request_param = sig.parameters.get("request")

                        if request_param:

                            def wrapper_with_request(request: Any) -> Any:
                                return func

                            wrapper_func = wrapper_with_request
                            wrapper_func.__name__ = func.__name__
                            wrapper_func.__annotations__ = {}
                        else:

                            def wrapper_no_request() -> Any:
                                return func

                            wrapper_func = wrapper_no_request
                            wrapper_func.__name__ = func.__name__
                            wrapper_func.__annotations__ = {}

                        # Store metadata
                        fixture_name = func.__name__
                        _INJECTED_FIXTURES[fixture_name] = {
                            "func": func,
                            "injected_params": injected_params,
                            "annotations": annotations,
                        }
                        logger.debug(
                            f"Registered injectable fixture '{fixture_name}' "
                            f"with params: {injected_params}"
                        )

                        # Call original decorator with the wrapper
                        result = original_fixture_decorator(*args, **kwargs)(
                            wrapper_func
                        )
                        # Store original func on the result
                        result._anydi_original_func = func  # type: ignore[attr-defined]
                        result._anydi_injected_params = injected_params  # type: ignore[attr-defined]
                        result._anydi_annotations = annotations  # type: ignore[attr-defined]
                        return result

                # No inject marker - proceed normally
                result = original_fixture_decorator(*args, **kwargs)(func)
                return result

            return decorator

    # Replace pytest.fixture
    pytest.fixture = patched_fixture  # type: ignore[assignment]
    # Also patch _pytest.fixtures.fixture
    import _pytest.fixtures

    _pytest.fixtures.fixture = patched_fixture  # type: ignore[assignment]
