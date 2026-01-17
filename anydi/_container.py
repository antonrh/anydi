"""AnyDI core implementation module."""

from __future__ import annotations

import contextlib
import importlib
import inspect
import logging
import types
import uuid
import warnings
from collections import defaultdict
from collections.abc import AsyncIterator, Callable, Iterable, Iterator, Sequence
from contextvars import ContextVar
from typing import Any, TypeVar, get_args, get_origin, overload

from typing_extensions import ParamSpec, Self, type_repr

from ._context import InstanceContext
from ._decorators import is_provided
from ._injector import Injector
from ._marker import Marker
from ._module import ModuleDef, ModuleRegistrar
from ._provider import Provider, ProviderDef, ProviderKind, ProviderParameter
from ._resolver import Resolver
from ._scanner import PackageOrIterable, Scanner
from ._types import NOT_SET, Event, Scope, is_event_type, is_iterator_type, is_none_type

T = TypeVar("T", bound=Any)
P = ParamSpec("P")


class Container:
    """AnyDI is a dependency injection container."""

    def __init__(
        self,
        *,
        providers: Iterable[ProviderDef] | None = None,
        modules: Iterable[ModuleDef] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._providers: dict[Any, Provider] = {}
        self._logger = logger or logging.getLogger(__name__)
        self._scopes: dict[str, Sequence[str]] = {
            "transient": ("transient", "singleton"),
            "singleton": ("singleton",),
        }

        self._resources: dict[str, list[Any]] = defaultdict(list)
        self._singleton_context = InstanceContext()
        self._scoped_context: dict[str, ContextVar[InstanceContext]] = {}

        # Components
        self._resolver = Resolver(self)
        self._injector = Injector(self)
        self._modules = ModuleRegistrar(self)
        self._scanner = Scanner(self)

        # Register default scopes
        self.register_scope("request")

        # Register self as provider
        self.register(Container, lambda: self, scope="singleton")

        # Register providers
        providers = providers or []
        for provider in providers:
            self._register_provider(
                provider.dependency_type,
                provider.factory,
                provider.scope,
                provider.from_context,
                False,
                None,
            )

        # Register modules
        modules = modules or []
        for module in modules:
            self.register_module(module)

    # == Container Properties ==

    @property
    def providers(self) -> dict[type[Any], Provider]:
        """Get the registered providers."""
        return self._providers

    @property
    def logger(self) -> logging.Logger:
        """Get the logger instance."""
        return self._logger

    # == Context & Lifespan Management ==

    def __enter__(self) -> Self:
        """Enter the singleton context."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> Any:
        """Exit the singleton context."""
        return self._singleton_context.__exit__(exc_type, exc_val, exc_tb)

    def start(self) -> None:
        """Start the singleton context."""
        # Resolve all singleton resources
        for dependency_type in self._resources.get("singleton", []):
            self.resolve(dependency_type)

    def close(self) -> None:
        """Close the singleton context."""
        self._singleton_context.close()

    async def __aenter__(self) -> Self:
        """Enter the singleton context."""
        await self.astart()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> bool:
        """Exit the singleton context."""
        return await self._singleton_context.__aexit__(exc_type, exc_val, exc_tb)

    async def astart(self) -> None:
        """Start the singleton context asynchronously."""
        for dependency_type in self._resources.get("singleton", []):
            await self.aresolve(dependency_type)

    async def aclose(self) -> None:
        """Close the singleton context asynchronously."""
        await self._singleton_context.aclose()

    @contextlib.contextmanager
    def scoped_context(self, scope: str) -> Iterator[InstanceContext]:
        """Obtain a context manager for the request-scoped context."""
        context_var = self._get_scoped_context_var(scope)

        # Check if context already exists (re-entering same scope)
        context = context_var.get(None)
        if context is not None:
            # Reuse existing context, don't create a new one
            yield context
            return

        # Create new context
        context = InstanceContext()
        token = context_var.set(context)

        # Resolve all request resources
        for dependency_type in self._resources.get(scope, []):
            if not is_event_type(dependency_type):
                continue
            self.resolve(dependency_type)

        with context:
            yield context
            context_var.reset(token)

    @contextlib.asynccontextmanager
    async def ascoped_context(self, scope: str) -> AsyncIterator[InstanceContext]:
        """Obtain a context manager for the specified scoped context."""
        context_var = self._get_scoped_context_var(scope)

        # Check if context already exists (re-entering same scope)
        context = context_var.get(None)
        if context is not None:
            # Reuse existing context, don't create a new one
            yield context
            return

        # Create new context
        context = InstanceContext()
        token = context_var.set(context)

        # Resolve all request resources
        for dependency_type in self._resources.get(scope, []):
            if not is_event_type(dependency_type):
                continue
            await self.aresolve(dependency_type)

        async with context:
            yield context
            context_var.reset(token)

    @contextlib.contextmanager
    def request_context(self) -> Iterator[InstanceContext]:
        """Obtain a context manager for the request-scoped context."""
        with self.scoped_context("request") as context:
            yield context

    @contextlib.asynccontextmanager
    async def arequest_context(self) -> AsyncIterator[InstanceContext]:
        """Obtain an async context manager for the request-scoped context."""
        async with self.ascoped_context("request") as context:
            yield context

    def _get_scoped_context(self, scope: str) -> InstanceContext:
        scoped_context_var = self._get_scoped_context_var(scope)
        try:
            scoped_context = scoped_context_var.get()
        except LookupError as exc:
            raise LookupError(
                f"The {scope} context has not been started. Please ensure that "
                f"the {scope} context is properly initialized before attempting "
                "to use it."
            ) from exc
        return scoped_context

    def _get_scoped_context_var(self, scope: str) -> ContextVar[InstanceContext]:
        """Get the context variable for the specified scope."""
        # Validate that scope is registered and not reserved
        if scope in ("transient", "singleton"):
            raise ValueError(
                f"Cannot get context variable for reserved scope `{scope}`."
            )
        if scope not in self._scopes:
            raise ValueError(
                f"Cannot get context variable for not registered scope `{scope}`. "
                f"Please register the scope first using register_scope()."
            )

        if scope not in self._scoped_context:
            self._scoped_context[scope] = ContextVar(f"{scope}_context")
        return self._scoped_context[scope]

    def _get_instance_context(self, scope: Scope) -> InstanceContext:
        """Get the instance context for the specified scope."""
        if scope == "singleton":
            return self._singleton_context
        return self._get_scoped_context(scope)

    # == Scopes == #

    def register_scope(
        self, scope: str, *, parents: Sequence[str] | None = None
    ) -> None:
        """Register a new scope with the specified parents."""
        # Check if the scope is reserved
        if scope in ("transient", "singleton"):
            raise ValueError(
                f"The scope `{scope}` is reserved and cannot be overridden."
            )

        # Check if the scope is already registered
        if scope in self._scopes:
            raise ValueError(f"The scope `{scope}` is already registered.")

        # Validate parents
        parents = parents or []
        for parent in parents:
            if parent not in self._scopes:
                raise ValueError(f"The parent scope `{parent}` is not registered.")

        # Register the scope
        self._scopes[scope] = tuple({scope, "singleton"} | set(parents))

    def has_scope(self, scope: str) -> bool:
        """Check if a scope is registered."""
        return scope in self._scopes

    def get_context_scopes(self, scopes: set[Scope] | None = None) -> list[str]:  # noqa: C901
        """Return scopes that require context management in dependency order."""
        # Build execution order: singleton -> request -> custom (by depth)
        ordered = ["singleton"]
        custom_scopes: list[tuple[int, str]] = []
        has_request = False

        for scope, parents in self._scopes.items():
            if scope == "singleton":
                continue
            if scope == "request":
                has_request = True
                continue
            if scope == "transient":
                continue
            custom_scopes.append((len(parents), scope))

        if has_request:
            ordered.append("request")

        custom_scopes.sort(key=lambda item: item[0])
        ordered.extend(scope for _, scope in custom_scopes)

        # If no filter, return all scopes with contexts (transient excluded)
        if scopes is None:
            return ordered

        # Helper to add scope with its parents to needed set
        def add_scope_tree(needed: set[str], scope: str) -> None:
            if scope == "singleton":
                needed.add("singleton")
            elif scope != "transient":
                needed.update(self._scopes[scope])

        needed_scopes: set[str] = set()

        # Add injected scopes and their parents
        for scope in scopes:
            add_scope_tree(needed_scopes, scope)

        # Add scopes with resource providers and their parents
        for scope in ordered:
            if self._resources.get(scope):
                add_scope_tree(needed_scopes, scope)

        return [scope for scope in ordered if scope in needed_scopes]

    # == Provider Registry ==

    def register(
        self,
        dependency_type: Any = NOT_SET,
        factory: Callable[..., Any] = NOT_SET,
        *,
        scope: Scope = "singleton",
        from_context: bool = False,
        override: bool = False,
        interface: Any = NOT_SET,
        call: Callable[..., Any] = NOT_SET,
    ) -> Provider:
        """Register a provider for the specified dependency type."""
        if interface is not NOT_SET:
            warnings.warn(
                "The `interface` is deprecated. Use `dependency_type` instead.",
                DeprecationWarning,
                stacklevel=2,
            )
        if call is not NOT_SET:
            warnings.warn(
                "The `call` is deprecated. Use `factory` instead.",
                DeprecationWarning,
                stacklevel=2,
            )

        if dependency_type is NOT_SET:
            dependency_type = interface
        if factory is NOT_SET:
            factory = call if call is not NOT_SET else dependency_type
        return self._register_provider(
            dependency_type, factory, scope, from_context, override, None
        )

    def is_registered(self, dependency_type: Any, /) -> bool:
        """Check if a provider is registered for the specified dependency type."""
        return dependency_type in self._providers

    def has_provider_for(self, dependency_type: Any, /) -> bool:
        """Check if a provider exists for the specified dependency type."""
        return self.is_registered(dependency_type) or is_provided(dependency_type)

    def unregister(self, dependency_type: Any, /) -> None:
        """Unregister a provider by dependency type."""
        if not self.is_registered(dependency_type):
            raise LookupError(
                f"The provider `{type_repr(dependency_type)}` is not registered."
            )

        provider = self._get_provider(dependency_type)

        # Cleanup instance context
        if provider.scope != "transient":
            try:
                context = self._get_instance_context(provider.scope)
            except LookupError:
                pass
            else:
                del context[dependency_type]

        # Cleanup provider references
        self._delete_provider(provider)

    def provider(
        self, *, scope: Scope, override: bool = False
    ) -> Callable[[Callable[P, T]], Callable[P, T]]:
        """Decorator to register a provider function with the specified scope."""

        def decorator(call: Callable[P, T]) -> Callable[P, T]:
            self._register_provider(NOT_SET, call, scope, False, override, None)
            return call

        return decorator

    def _register_provider(  # noqa: C901
        self,
        dependency_type: Any,
        factory: Callable[..., Any],
        scope: Scope,
        from_context: bool,
        override: bool,
        defaults: dict[str, Any] | None,
    ) -> Provider:
        """Register a provider with the specified scope."""
        # Validate scope is registered
        if scope not in self._scopes:
            raise ValueError(
                f"The scope `{scope}` is not registered. "
                "Please register the scope first using register_scope()."
            )

        # Default factory to dependency_type if not set
        if not from_context and factory is NOT_SET:
            factory = dependency_type

        # Handle from_context providers (context-provided dependencies)
        if from_context:
            if scope in ("singleton", "transient"):
                raise ValueError(
                    f"The `from_context=True` option cannot be used with "
                    f"`{scope}` scope. Use a scoped context like 'request' instead."
                )
            if dependency_type is NOT_SET:
                raise TypeError(
                    "The `dependency_type` parameter is required when using "
                    "`from_context=True`."
                )
            name = type_repr(dependency_type)
            if dependency_type in self._providers and not override:
                raise LookupError(f"The provider `{name}` is already registered.")

            provider = Provider(
                dependency_type=dependency_type,
                factory=lambda: None,
                scope=scope,
                from_context=True,
                name=name,
                parameters=(),
                is_class=False,
                is_coroutine=False,
                is_generator=False,
                is_async_generator=False,
                is_async=False,
                is_resource=False,
            )
        else:
            # Regular provider registration
            name = type_repr(factory)
            kind = ProviderKind.from_call(factory)
            is_class = kind == ProviderKind.CLASS
            is_coroutine = kind == ProviderKind.COROUTINE
            is_generator = kind == ProviderKind.GENERATOR
            is_async_generator = kind == ProviderKind.ASYNC_GENERATOR
            is_resource = is_generator or is_async_generator

            if scope == "transient" and is_resource:
                raise TypeError(
                    f"The resource provider `{name}` is attempting to register "
                    "with a transient scope, which is not allowed."
                )

            signature = inspect.signature(factory, eval_str=True)

            # Detect dependency_type from factory or return annotation
            if dependency_type is NOT_SET:
                dependency_type = factory if is_class else signature.return_annotation
                if dependency_type is inspect.Signature.empty:
                    dependency_type = None

            # Unwrap iterator types for resources
            type_origin = get_origin(dependency_type)
            if is_iterator_type(dependency_type) or is_iterator_type(type_origin):
                args = get_args(dependency_type)
                if not args:
                    raise TypeError(
                        f"Cannot use `{name}` resource type annotation "
                        "without actual type argument."
                    )
                dependency_type = args[0]
                if is_none_type(dependency_type):
                    dependency_type = type(f"Event_{uuid.uuid4().hex}", (Event,), {})

            if is_none_type(dependency_type):
                raise TypeError(f"Missing `{name}` provider return annotation.")

            if dependency_type in self._providers and not override:
                raise LookupError(
                    f"The provider `{type_repr(dependency_type)}` is already "
                    "registered."
                )

            # Process parameters
            parameters: list[ProviderParameter] = []
            unresolved_parameter: inspect.Parameter | None = None
            unresolved_exc: LookupError | None = None
            scope_hierarchy = (
                self._scopes.get(scope, ()) if scope != "transient" else ()
            )

            for param in signature.parameters.values():
                if param.annotation is inspect.Parameter.empty:
                    raise TypeError(
                        f"Missing provider `{name}` "
                        f"dependency `{param.name}` annotation."
                    )
                if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                    raise TypeError(
                        f"Positional-only parameters "
                        f"are not allowed in the provider `{name}`."
                    )

                has_default = param.default is not inspect.Parameter.empty
                default = param.default if has_default else NOT_SET

                try:
                    sub_provider = self._get_or_register_provider(param.annotation)
                except LookupError as exc:
                    if (defaults and param.name in defaults) or has_default:
                        continue
                    unresolved_parameter = param
                    unresolved_exc = exc
                    continue

                if scope_hierarchy and sub_provider.scope not in scope_hierarchy:
                    raise ValueError(
                        f"The provider `{name}` with a `{scope}` scope "
                        f"cannot depend on `{sub_provider}` with a "
                        f"`{sub_provider.scope}` scope. Please ensure all "
                        "providers are registered with matching scopes."
                    )

                parameters.append(
                    ProviderParameter(
                        dependency_type=param.annotation,
                        name=param.name,
                        default=default,
                        has_default=has_default,
                        provider=sub_provider,
                        shared_scope=(
                            sub_provider.scope == scope and scope != "transient"
                        ),
                    )
                )

            if unresolved_parameter:
                raise LookupError(
                    f"The provider `{name}` depends on "
                    f"`{unresolved_parameter.name}` of type "
                    f"`{type_repr(unresolved_parameter.annotation)}`, which has not "
                    "been registered or set. To resolve this, ensure that "
                    f"`{unresolved_parameter.name}` is registered before attempting "
                    "to use it, or register it with `from_context=True` if it "
                    "should be provided via scoped context."
                ) from unresolved_exc

            provider = Provider(
                dependency_type=dependency_type,
                factory=factory,
                scope=scope,
                from_context=False,
                name=name,
                parameters=tuple(parameters),
                is_class=is_class,
                is_coroutine=is_coroutine,
                is_generator=is_generator,
                is_async_generator=is_async_generator,
                is_async=is_coroutine or is_async_generator,
                is_resource=is_resource,
            )

        self._set_provider(provider)
        if override:
            self._resolver.clear_caches()
        return provider

    def _get_provider(self, dependency_type: Any) -> Provider:
        """Get provider by dependency type."""
        try:
            return self._providers[dependency_type]
        except KeyError:
            raise LookupError(
                f"The provider for `{type_repr(dependency_type)}` has "
                "not been registered. Please ensure that the provider is "
                "properly registered before attempting to use it."
            ) from None

    def _get_or_register_provider(
        self, dependency_type: Any, defaults: dict[str, Any] | None = None
    ) -> Provider:
        """Get or register a provider by dependency type."""
        try:
            return self._get_provider(dependency_type)
        except LookupError:
            if inspect.isclass(dependency_type) and is_provided(dependency_type):
                return self._register_provider(
                    dependency_type,
                    dependency_type,
                    dependency_type.__provided__.get("scope", "singleton"),
                    dependency_type.__provided__.get("from_context", False),
                    False,
                    defaults,
                )
            raise LookupError(
                f"The provider `{type_repr(dependency_type)}` is either not "
                "registered, not provided, or not set in the scoped context. "
                "Please ensure that the provider is properly registered and "
                "that the class is decorated with a scope before attempting to use it."
            ) from None

    def _set_provider(self, provider: Provider) -> None:
        """Set a provider by dependency type."""
        self._providers[provider.dependency_type] = provider
        if provider.is_resource:
            self._resources[provider.scope].append(provider.dependency_type)

    def _delete_provider(self, provider: Provider) -> None:
        """Delete a provider."""
        if provider.dependency_type in self._providers:
            del self._providers[provider.dependency_type]
        if provider.is_resource:
            self._resources[provider.scope].remove(provider.dependency_type)

    # == Instance Resolution ==

    @overload
    def resolve(self, dependency_type: type[T], /) -> T: ...

    @overload
    def resolve(self, dependency_type: T, /) -> T: ...  # type: ignore

    def resolve(self, dependency_type: type[T], /) -> T:
        """Resolve an instance by dependency type using compiled sync resolver."""
        cached = self._resolver.get_cached(dependency_type, is_async=False)
        if cached is not None:
            return cached.resolve(self)

        provider = self._get_or_register_provider(dependency_type)
        compiled = self._resolver.compile(provider, is_async=False)
        return compiled.resolve(self)

    @overload
    async def aresolve(self, dependency_type: type[T], /) -> T: ...

    @overload
    async def aresolve(self, dependency_type: T, /) -> T: ...

    async def aresolve(self, dependency_type: type[T], /) -> T:
        """Resolve an instance by dependency type asynchronously."""
        cached = self._resolver.get_cached(dependency_type, is_async=True)
        if cached is not None:
            return await cached.resolve(self)

        provider = self._get_or_register_provider(dependency_type)
        compiled = self._resolver.compile(provider, is_async=True)
        return await compiled.resolve(self)

    def create(self, dependency_type: type[T], /, **defaults: Any) -> T:
        """Create an instance by dependency type."""
        if not defaults:
            cached = self._resolver.get_cached(dependency_type, is_async=False)
            if cached is not None:
                return cached.create(self, None)

        provider = self._get_or_register_provider(dependency_type, defaults)
        compiled = self._resolver.compile(provider, is_async=False)
        return compiled.create(self, defaults or None)

    async def acreate(self, dependency_type: type[T], /, **defaults: Any) -> T:
        """Create an instance by dependency type asynchronously."""
        if not defaults:
            cached = self._resolver.get_cached(dependency_type, is_async=True)
            if cached is not None:
                return await cached.create(self, None)

        provider = self._get_or_register_provider(dependency_type, defaults)
        compiled = self._resolver.compile(provider, is_async=True)
        return await compiled.create(self, defaults or None)

    def is_resolved(self, dependency_type: Any, /) -> bool:
        """Check if an instance for the dependency type exists."""
        try:
            provider = self._get_provider(dependency_type)
        except LookupError:
            return False
        if provider.scope == "transient":
            return False
        context = self._get_instance_context(provider.scope)
        return dependency_type in context

    def release(self, dependency_type: Any, /) -> None:
        """Release an instance by dependency type."""
        provider = self._get_provider(dependency_type)
        if provider.scope == "transient":
            return None
        context = self._get_instance_context(provider.scope)
        del context[dependency_type]

    def reset(self) -> None:
        """Reset resolved instances."""
        for dependency_type, provider in self._providers.items():
            if provider.scope == "transient":
                continue
            try:
                context = self._get_instance_context(provider.scope)
            except LookupError:
                continue
            del context[dependency_type]

    # == Injection Utilities ==

    @overload
    def inject(self, func: Callable[P, T]) -> Callable[P, T]: ...

    @overload
    def inject(self) -> Callable[[Callable[P, T]], Callable[P, T]]: ...

    def inject(
        self, func: Callable[P, T] | None = None
    ) -> Callable[[Callable[P, T]], Callable[P, T]] | Callable[P, T]:
        """Decorator to inject dependencies into a callable."""

        def decorator(call: Callable[P, T]) -> Callable[P, T]:
            return self._injector.inject(call)

        if func is None:
            return decorator
        return decorator(func)

    def run(self, func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
        """Run the given function with injected dependencies."""
        return self._injector.inject(func)(*args, **kwargs)

    def validate_injected_parameter(
        self, parameter: inspect.Parameter, *, call: Callable[..., Any]
    ) -> tuple[Any, bool, Marker | None]:
        """Validate an injected parameter."""
        return self._injector.validate_parameter(parameter, call=call)

    # == Module Registration ==

    def register_module(self, module: ModuleDef) -> None:
        """Register a module as a callable, module type, or module instance."""
        self._modules.register(module)

    # == Package Scanning ==

    def scan(
        self, /, packages: PackageOrIterable, *, tags: Iterable[str] | None = None
    ) -> None:
        self._scanner.scan(packages=packages, tags=tags)

    # == Testing / Override Support ==

    @contextlib.contextmanager
    def override(
        self,
        dependency_type: Any = NOT_SET,
        /,
        instance: Any = NOT_SET,
        *,
        interface: Any = NOT_SET,
    ) -> Iterator[None]:
        """Override a dependency with a specific instance for testing."""
        if interface is not NOT_SET:
            warnings.warn(
                "The `interface` is deprecated. Use `dependency_type` instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            if dependency_type is NOT_SET:
                dependency_type = interface

        if dependency_type is NOT_SET:
            raise TypeError("override() missing required argument: 'dependency_type'")

        if instance is NOT_SET:
            raise TypeError("override() missing required argument: 'instance'")

        if not self.has_provider_for(dependency_type):
            raise LookupError(
                f"The provider `{type_repr(dependency_type)}` is not registered."
            )
        self._resolver.add_override(dependency_type, instance)
        try:
            yield
        finally:
            self._resolver.remove_override(dependency_type)


def import_container(container_path: str) -> Container:
    """Import container from a string path."""
    # Replace colon with dot for unified processing
    container_path = container_path.replace(":", ".")

    try:
        module_path, attr_name = container_path.rsplit(".", 1)
    except ValueError as exc:
        raise ImportError(
            f"Invalid container path '{container_path}'. "
            "Expected format: 'module.path:attribute' or 'module.path.attribute'"
        ) from exc

    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ImportError(
            f"Failed to import module '{module_path}' "
            f"from container path '{container_path}'"
        ) from exc

    try:
        container_or_factory = getattr(module, attr_name)
    except AttributeError as exc:
        raise ImportError(
            f"Module '{module_path}' has no attribute '{attr_name}'"
        ) from exc

    # If it's a callable (factory), call it
    if callable(container_or_factory) and not isinstance(
        container_or_factory, Container
    ):
        container = container_or_factory()
    else:
        container = container_or_factory

    if not isinstance(container, Container):
        raise ImportError(
            f"Expected Container instance, got {type(container).__name__} "
            f"from '{container_path}'"
        )

    return container
