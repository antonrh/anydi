from __future__ import annotations

import importlib.util
import inspect
import logging
import warnings
from collections.abc import Callable, Iterator
from typing import Annotated, Any, cast, get_args, get_origin

import pytest
from anyio.pytest_plugin import extract_backend_and_options, get_runner
from typing_extensions import get_annotations

from anydi import Container, import_container
from anydi._marker import is_marker

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
        "anydi_fixture_inject_enabled",
        help="Enable dependency injection into fixtures (via Provide[T] or autoinject)",
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


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "inject: mark test as needing dependency injection (deprecated)",
    )

    # Patch pytest fixtures to support explicit injection markers (Provide[T])
    # Only active when anydi_fixture_inject_enabled=true
    _patch_pytest_fixtures()


@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(  # noqa: C901
    fixturedef: pytest.FixtureDef[Any],
    request: pytest.FixtureRequest,
) -> Iterator[None]:
    """Inject dependencies into fixtures.

    Only active when anydi_fixture_inject_enabled=true.
    Handles:
    - Fixtures with explicit markers (Provide[T], Annotated[T, Inject()])
    - Fixtures with anydi_autoinject=true (auto-injection for all)
    """
    fixture_name = fixturedef.argname

    # Skip container fixture to avoid circular dependency
    if fixture_name == "container":
        yield
        return

    # Check if fixture injection is enabled at all
    fixture_inject_enabled = cast(
        bool, request.config.getini("anydi_fixture_inject_enabled")
    )
    if not fixture_inject_enabled:
        yield
        return

    # Check if this fixture was registered via explicit markers (Provide[T])
    if fixture_name in _INJECTED_FIXTURES:
        fixture_info = _INJECTED_FIXTURES[fixture_name]
        original_func = fixture_info["func"]
        parameters: list[tuple[str, Any]] = fixture_info["parameters"]
    else:
        # Check if autoinject is enabled for automatic injection
        autoinject = cast(bool, request.config.getini("anydi_autoinject"))
        inject_all = cast(bool, request.config.getini("anydi_inject_all"))
        if not (autoinject or inject_all):
            yield
            return

        # For autoinject mode, get all parameters from the fixture function
        original_func = fixturedef.func
        parameters = [
            (name, annotation)
            for name, annotation, _ in _iter_explicit_injectable_parameters(
                original_func
            )
        ]
        if not parameters:
            yield
            return

    # Get the container
    try:
        container = cast(Container, request.getfixturevalue("container"))
    except pytest.FixtureLookupError:
        yield
        return

    resolvable_params = _select_resolvable_parameters(container, parameters)

    if not resolvable_params:
        yield
        return

    target_name = f"fixture '{fixture_name}'"

    def _prepare_sync_call_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
        combined_kwargs = dict(kwargs)
        combined_kwargs.update(
            _resolve_dependencies_sync(container, resolvable_params, target=target_name)
        )
        return combined_kwargs

    async def _prepare_async_call_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
        combined_kwargs = dict(kwargs)
        combined_kwargs.update(
            await _resolve_dependencies_async(
                container, resolvable_params, target=target_name
            )
        )
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

            async def _fixture() -> Any:
                call_kwargs = await _prepare_async_call_kwargs(kwargs)
                async for value in original_func(**call_kwargs):
                    yield value

            with get_runner(backend_name, backend_options) as runner:
                yield from runner.run_asyncgen_fixture(_fixture, {})  # type: ignore

        fixturedef.func = asyncgen_wrapper  # type: ignore[misc]
    elif inspect.iscoroutinefunction(original_func):

        def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            backend_name, backend_options = _ensure_anyio_backend()

            async def _fixture() -> Any:
                call_kwargs = await _prepare_async_call_kwargs(kwargs)
                return await original_func(**call_kwargs)

            with get_runner(backend_name, backend_options) as runner:
                return runner.run_fixture(_fixture, {})

        fixturedef.func = async_wrapper  # type: ignore[misc]
    elif inspect.isgeneratorfunction(original_func):

        def generator_wrapper(*args: Any, **kwargs: Any) -> Iterator[Any]:
            call_kwargs = _prepare_sync_call_kwargs(kwargs)
            yield from original_func(**call_kwargs)

        fixturedef.func = generator_wrapper  # type: ignore[misc]
    else:

        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            call_kwargs = _prepare_sync_call_kwargs(kwargs)
            return original_func(**call_kwargs)

        fixturedef.func = sync_wrapper  # type: ignore[misc]

    # Let pytest execute the modified fixture
    yield

    # Restore the original function
    fixturedef.func = original_fixture_func  # type: ignore[misc]


@pytest.fixture(scope="session")
def container(request: pytest.FixtureRequest) -> Container:
    """Container fixture with testing mode enabled."""
    container = _find_container(request)
    container.enable_test_mode()
    return container


def _get_test_injectable_params(
    request: pytest.FixtureRequest,
) -> tuple[list[tuple[str, Any]], bool]:
    """Get injectable parameters for a test function.

    Returns (parameters, uses_deprecated_marker) tuple.
    Parameters are [(name, annotation), ...] tuples for injection.
    """
    # Get parameter names that are not defined as fixtures (for autoinject mode)
    fixturenames = set(request.node._fixtureinfo.initialnames) - set(
        request.node._fixtureinfo.name2fixturedefs.keys()
    )

    marker = request.node.get_closest_marker("inject")
    autoinject = cast(bool, request.config.getini("anydi_autoinject"))
    inject_all = cast(bool, request.config.getini("anydi_inject_all"))

    if inject_all:
        logger.warning(
            "Configuration option 'anydi_inject_all' is deprecated. "
            "Please use 'anydi_autoinject' instead."
        )

    has_any_explicit = False
    explicit_params: list[tuple[str, Any]] = []
    all_params: list[tuple[str, Any]] = []

    for name, annotation, is_explicit in _iter_explicit_injectable_parameters(
        request.function
    ):
        # For explicit markers, always include them - they explicitly request injection
        if is_explicit:
            has_any_explicit = True
            explicit_params.append((name, annotation))
        # For autoinject mode, only include params not defined as fixtures
        elif name in fixturenames:
            all_params.append((name, annotation))

    # Priority logic:
    # 1. If any explicit markers (Provide[T], Inject()) -> use only explicit
    if has_any_explicit:
        return explicit_params, False

    # 2. If deprecated @pytest.mark.inject -> use all params + warn
    if marker is not None:
        return all_params, True

    # 3. If autoinject enabled -> use all params (no warning)
    if autoinject or inject_all:
        return all_params, False

    # 4. Otherwise -> no injection
    return [], False


@pytest.fixture(autouse=True)
def _anydi_inject(request: pytest.FixtureRequest) -> None:
    """Inject dependencies into sync test functions."""
    if inspect.iscoroutinefunction(request.function):
        return

    parameters, uses_deprecated = _get_test_injectable_params(request)
    if not parameters:
        return

    if uses_deprecated:
        warnings.warn(
            f"Using @pytest.mark.inject on test '{request.node.name}' is "
            "deprecated. Use Provide[T] or Annotated[T, Inject()] instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    container = cast(Container, request.getfixturevalue("container"))
    resolvable = _select_resolvable_parameters(container, parameters)
    if not resolvable:
        return

    resolved = _resolve_dependencies_sync(
        container, resolvable, target=request.node.nodeid
    )
    for argname, value in resolved.items():
        request.node.funcargs[argname] = value


@pytest.fixture(autouse=True)
def _anydi_ainject(request: pytest.FixtureRequest) -> None:
    """Inject dependencies into async test functions."""
    if not inspect.iscoroutinefunction(
        request.function
    ) and not inspect.isasyncgenfunction(request.function):
        return

    parameters, uses_deprecated = _get_test_injectable_params(request)
    if not parameters:
        return

    # Skip if the anyio backend is not available
    if "anyio_backend" not in request.fixturenames:
        msg = (
            "To run async test functions with `anyio`, "
            "please configure the `anyio` pytest plugin.\n"
            "See: https://anyio.readthedocs.io/en/stable/testing.html"
        )
        pytest.fail(msg, pytrace=False)

    if uses_deprecated:
        warnings.warn(
            f"Using @pytest.mark.inject on test '{request.node.name}' is "
            "deprecated. Use Provide[T] or Annotated[T, Inject()] instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    container = cast(Container, request.getfixturevalue("container"))
    resolvable = _select_resolvable_parameters(container, parameters)
    if not resolvable:
        return

    async def _awrapper() -> None:
        resolved = await _resolve_dependencies_async(
            container, resolvable, target=request.node.nodeid
        )
        for argname, value in resolved.items():
            request.node.funcargs[argname] = value

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


def _has_explicit_marker(annotation: Any) -> bool:
    """Check if parameter has explicit injection marker.

    Supports:
    - Provide[T] -> Annotated[T, Marker()]
    - Annotated[T, Inject()] -> marker in metadata
    """
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        if len(args) >= 2:
            for arg in args[1:]:
                if is_marker(arg):
                    return True
    return False


def _unwrap_annotation(annotation: Any) -> Any:
    """Unwrap Annotated type to get the actual type.

    Returns the unwrapped type (without Annotated marker wrapper).
    """
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        if len(args) >= 2:
            for arg in args[1:]:
                if is_marker(arg):
                    return args[0]
    return annotation


def _iter_explicit_injectable_parameters(
    func: Callable[..., Any], *, skip: tuple[str, ...] = ("request",)
) -> Iterator[tuple[str, Any, bool]]:
    """Iterate parameters returning (name, unwrapped_annotation, has_explicit_marker).

    For each parameter, returns:
    - name: parameter name
    - annotation: unwrapped type annotation (without Annotated marker wrapper)
    - has_explicit_marker: True if Provide[T] or Annotated[T, Inject()]
    """
    annotations = get_annotations(func, eval_str=True)
    skip_names = set(skip)

    for name, annotation in annotations.items():
        if name in skip_names or name == "return":
            continue

        has_marker = _has_explicit_marker(annotation)
        unwrapped = _unwrap_annotation(annotation)

        yield name, unwrapped, has_marker


def _patch_pytest_fixtures() -> None:  # noqa: C901
    """Patch pytest.fixture decorator to intercept fixtures with explicit markers.

    Only handles explicit markers: Provide[T], Annotated[T, Inject()].
    Auto-injection (anydi_autoinject) is handled in pytest_fixture_setup.

    Note: @pytest.mark.inject is NOT supported for fixtures (only for tests).
    """
    from _pytest.fixtures import fixture as original_fixture_decorator

    def patched_fixture(*args: Any, **kwargs: Any) -> Any:  # noqa: C901
        """Patched fixture decorator that handles explicit inject markers."""

        def get_explicit_injectable_params(
            func: Callable[..., Any],
        ) -> list[tuple[str, Any]]:
            """Get parameters with explicit injection markers.

            Returns list of (name, annotation) tuples for parameters marked with
            Provide[T] or Annotated[T, Inject()].
            """
            explicit_params: list[tuple[str, Any]] = []

            for name, annotation, is_explicit in _iter_explicit_injectable_parameters(
                func
            ):
                if is_explicit:
                    explicit_params.append((name, annotation))

            return explicit_params

        def register_fixture(func: Callable[..., Any]) -> Callable[..., Any] | None:
            parameters = get_explicit_injectable_params(func)
            if not parameters:
                return None

            sig = inspect.signature(func, eval_str=True)
            injected_param_names = {name for name, _ in parameters}

            # Build wrapper parameters: keep non-injected params for pytest resolution
            wrapper_params: list[inspect.Parameter] = []
            wrapper_annotations: dict[str, Any] = {}

            for param in sig.parameters.values():
                if param.name in injected_param_names:
                    # Skip injected params - they'll be provided by container
                    continue
                # Keep non-injected params for pytest fixture resolution
                wrapper_params.append(param)
                if param.annotation is not inspect.Parameter.empty:
                    wrapper_annotations[param.name] = param.annotation

            # Create wrapper that accepts non-injected params from pytest
            def wrapper_func(**kwargs: Any) -> Any:
                # The kwargs contain pytest fixtures, which will be merged with
                # injected params in pytest_fixture_setup
                del kwargs  # Used by pytest_fixture_setup hook, not here
                return func

            # Set wrapper signature and annotations for pytest fixture resolution
            wrapper_func.__name__ = func.__name__
            wrapper_func.__signature__ = sig.replace(parameters=wrapper_params)  # type: ignore[attr-defined]
            wrapper_func.__annotations__ = wrapper_annotations

            fixture_name = func.__name__
            _INJECTED_FIXTURES[fixture_name] = {
                "func": func,
                "parameters": parameters,
            }
            logger.debug(
                "Registered injectable fixture '%s' with params: %s",
                fixture_name,
                [name for name, _ in parameters],
            )

            return wrapper_func

        # Handle both @pytest.fixture and @pytest.fixture() usage
        if len(args) == 1 and callable(args[0]) and not kwargs:
            func = args[0]
            wrapper_func = register_fixture(func)
            if wrapper_func:
                return original_fixture_decorator(wrapper_func)

            return original_fixture_decorator(func)
        else:

            def decorator(func: Callable[..., Any]) -> Any:
                wrapper_func = register_fixture(func)
                if wrapper_func:
                    return original_fixture_decorator(*args, **kwargs)(wrapper_func)

                return original_fixture_decorator(*args, **kwargs)(func)

            return decorator

    # Replace pytest.fixture
    pytest.fixture = patched_fixture  # type: ignore[assignment]
    # Also patch _pytest.fixtures.fixture
    import _pytest.fixtures

    _pytest.fixtures.fixture = patched_fixture  # type: ignore[assignment]


def _select_resolvable_parameters(
    container: Container,
    parameters: Iterator[tuple[str, Any]] | list[tuple[str, Any]],
) -> list[tuple[str, Any]]:
    return [
        (name, annotation)
        for name, annotation in parameters
        if container.has_provider_for(annotation)
    ]


def _resolve_dependencies_sync(
    container: Container,
    parameters: list[tuple[str, Any]],
    *,
    target: str,
) -> dict[str, Any]:
    container.enable_test_mode()
    resolved: dict[str, Any] = {}
    for param_name, annotation in parameters:
        try:
            resolved[param_name] = container.resolve(annotation)
            logger.debug("Resolved %s=%s for %s", param_name, annotation, target)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning(
                "Failed to resolve dependency for '%s' on %s.",
                param_name,
                target,
                exc_info=exc,
            )
    return resolved


async def _resolve_dependencies_async(
    container: Container,
    parameters: list[tuple[str, Any]],
    *,
    target: str,
) -> dict[str, Any]:
    container.enable_test_mode()
    resolved: dict[str, Any] = {}
    for param_name, annotation in parameters:
        try:
            resolved[param_name] = await container.aresolve(annotation)
            logger.debug("Resolved %s=%s for async %s", param_name, annotation, target)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning(
                "Failed to resolve async dependency for '%s' on %s.",
                param_name,
                target,
                exc_info=exc,
            )
    return resolved
