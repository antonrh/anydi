"""AnyDI core implementation module."""

from __future__ import annotations

import contextlib
import importlib
import inspect
import logging
import types
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator, Callable, Iterable, Iterator, Sequence
from contextvars import ContextVar
from typing import Any, TypeVar, get_args, get_origin, overload

from typing_extensions import ParamSpec, Self, type_repr

from ._context import InstanceContext
from ._decorators import is_provided
from ._injector import Injector
from ._marker import Marker, is_from_context_marker, unwrap_from_context
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

        # Build state
        self._built = False

        # Register default scopes
        self.register_scope("request")

        # Register self as provider
        self._register_provider(
            lambda: self,
            "singleton",
            Container,
        )

        # Register providers
        providers = providers or []
        for provider in providers:
            self._register_provider(
                provider.call,
                provider.scope,
                provider.interface,
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
        for interface in self._resources.get("singleton", []):
            self.resolve(interface)

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
        for interface in self._resources.get("singleton", []):
            await self.aresolve(interface)

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
        for interface in self._resources.get(scope, []):
            if not is_event_type(interface):
                continue
            self.resolve(interface)

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
        for interface in self._resources.get(scope, []):
            if not is_event_type(interface):
                continue
            await self.aresolve(interface)

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
        interface: Any,
        call: Callable[..., Any] = NOT_SET,
        *,
        scope: Scope = "singleton",
        override: bool = False,
    ) -> Provider:
        """Register a provider for the specified interface."""
        if self._built and not override:
            raise RuntimeError(
                "Cannot register providers after build() has been called. "
                "All providers must be registered before building the container."
            )
        if call is NOT_SET:
            call = interface
        return self._register_provider(call, scope, interface, override)

    def is_registered(self, interface: Any) -> bool:
        """Check if a provider is registered for the specified interface."""
        return interface in self._providers

    def has_provider_for(self, interface: Any) -> bool:
        """Check if a provider exists for the specified interface."""
        return self.is_registered(interface) or is_provided(interface)

    def unregister(self, interface: Any) -> None:
        """Unregister a provider by interface."""
        if not self.is_registered(interface):
            raise LookupError(
                f"The provider interface `{type_repr(interface)}` not registered."
            )

        provider = self._get_provider(interface)

        # Cleanup instance context
        if provider.scope != "transient":
            try:
                context = self._get_instance_context(provider.scope)
            except LookupError:
                pass
            else:
                del context[interface]

        # Cleanup provider references
        self._delete_provider(provider)

    def provider(
        self, *, scope: Scope, override: bool = False
    ) -> Callable[[Callable[P, T]], Callable[P, T]]:
        """Decorator to register a provider function with the specified scope."""

        def decorator(call: Callable[P, T]) -> Callable[P, T]:
            self._register_provider(call, scope, NOT_SET, override)
            return call

        return decorator

    def _register_provider(  # noqa: C901
        self,
        call: Callable[..., Any],
        scope: Scope,
        interface: Any = NOT_SET,
        override: bool = False,
        defaults: dict[str, Any] | None = None,
    ) -> Provider:
        """Register a provider with the specified scope."""
        name = type_repr(call)
        kind = ProviderKind.from_call(call)
        is_class = kind == ProviderKind.CLASS
        is_coroutine = kind == ProviderKind.COROUTINE
        is_generator = kind == ProviderKind.GENERATOR
        is_async_generator = kind == ProviderKind.ASYNC_GENERATOR
        is_resource = is_generator or is_async_generator

        # Validate scope
        self._validate_provider_scope(scope, name, is_resource)

        # Get signature and detect interface
        signature = inspect.signature(call, eval_str=True)

        if interface is NOT_SET:
            interface = call if is_class else signature.return_annotation
            if interface is inspect.Signature.empty:
                interface = None

        # Handle iterator types for resources
        interface_origin = get_origin(interface)
        if is_iterator_type(interface) or is_iterator_type(interface_origin):
            if args := get_args(interface):
                interface = args[0]
                if is_none_type(interface):
                    interface = type(f"Event_{uuid.uuid4().hex}", (Event,), {})
            else:
                raise TypeError(
                    f"Cannot use `{name}` resource type annotation "
                    "without actual type argument."
                )

        # Validate interface
        if is_none_type(interface):
            raise TypeError(f"Missing `{name}` provider return annotation.")

        if interface in self._providers and not override:
            raise LookupError(
                f"The provider interface `{type_repr(interface)}` already registered."
            )

        # Process parameters
        parameters: list[ProviderParameter] = []

        for parameter in signature.parameters.values():
            annotation = parameter.annotation

            if annotation is inspect.Parameter.empty:
                raise TypeError(
                    f"Missing provider `{name}` "
                    f"dependency `{parameter.name}` annotation."
                )
            if parameter.kind == inspect.Parameter.POSITIONAL_ONLY:
                raise TypeError(
                    "Positional-only parameters "
                    f"are not allowed in the provider `{name}`."
                )

            has_default = parameter.default is not inspect.Parameter.empty
            default = parameter.default if has_default else NOT_SET

            # Skip parameters provided via defaults (for create() method)
            if defaults and parameter.name in defaults:
                continue

            # Lazy registration: Store parameter without resolving dependencies
            # Keep original annotation (including FromContext) for later resolution
            parameters.append(
                ProviderParameter(
                    name=parameter.name,
                    annotation=annotation,
                    default=default,
                    has_default=has_default,
                    provider=None,  # Lazy - will be resolved in build()
                    shared_scope=False,  # Lazy - will be computed in build()
                )
            )

        # Create and register provider
        provider = Provider(
            call=call,
            scope=scope,
            interface=interface,
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

    def _validate_provider_scope(
        self, scope: Scope, name: str, is_resource: bool
    ) -> None:
        """Validate the provider scope."""
        if scope not in self._scopes:
            raise ValueError(
                f"The provider `{name}` scope is invalid. Only the following "
                f"scopes are supported: {', '.join(self._scopes.keys())}. "
                "Please use one of the supported scopes when registering a provider."
            )
        if scope == "transient" and is_resource:
            raise TypeError(
                f"The resource provider `{name}` is attempting to register "
                "with a transient scope, which is not allowed."
            )

    def _get_provider(self, interface: Any) -> Provider:
        """Get provider by interface."""
        try:
            return self._providers[interface]
        except KeyError:
            raise LookupError(
                f"The provider interface for `{type_repr(interface)}` has "
                "not been registered. Please ensure that the provider interface is "
                "properly registered before attempting to use it."
            ) from None

    def _get_or_register_provider(
        self, interface: Any, defaults: dict[str, Any] | None = None
    ) -> Provider:
        """Get or register a provider by interface."""
        try:
            provider = self._get_provider(interface)
        except LookupError:
            if inspect.isclass(interface) and is_provided(interface):
                provider = self._register_provider(
                    interface,
                    interface.__provided__["scope"],
                    NOT_SET,
                    False,
                    defaults,
                )
            else:
                raise LookupError(
                    f"The provider interface `{type_repr(interface)}` is either not "
                    "registered, not provided, or not set in the scoped context. "
                    "Please ensure that the provider interface is properly "
                    "registered and that the class is decorated with a scope before "
                    "attempting to use it."
                ) from None

        # Ensure provider dependencies are resolved if not built yet
        if not self._built:
            provider = self._ensure_provider_resolved(provider, set())

        return provider

    def _ensure_provider_resolved(  # noqa: C901
        self, provider: Provider, resolving: set[Any]
    ) -> Provider:
        """Ensure dependencies are resolved, resolving on-the-fly if needed."""
        # Check if we're already resolving this provider (circular dependency)
        if provider.interface in resolving:
            return provider

        # Check if already resolved by examining parameters
        # A provider is resolved if all its parameters either:
        # 1. Have a provider set (provider is not None), OR
        # 2. Have a default value, OR
        # 3. Are marked for context.set() (provider=None but in unresolved list)
        all_resolved = all(
            param.provider is not None
            or param.has_default
            or (
                param.provider is None and param.shared_scope
            )  # Unresolved for context.set()
            for param in provider.parameters
        )
        if all_resolved:
            return provider

        # Mark as currently being resolved
        resolving = resolving | {provider.interface}

        # Resolve dependencies for this provider
        resolved_params: list[ProviderParameter] = []

        for param in provider.parameters:
            if param.provider is not None:
                # Already resolved
                resolved_params.append(param)
                continue

            # Check if marked with FromContext
            from_context = is_from_context_marker(param.annotation)
            annotation = (
                unwrap_from_context(param.annotation)
                if from_context
                else param.annotation
            )

            # Try to resolve the dependency
            # First check if this would create a circular dependency
            if annotation in resolving:
                # Circular dependency detected
                # For scoped providers with FromContext, leave unresolved
                if provider.scope not in ("singleton", "transient") and from_context:
                    resolved_params.append(
                        ProviderParameter(
                            name=param.name,
                            annotation=annotation,
                            default=param.default,
                            has_default=param.has_default,
                            provider=None,
                            shared_scope=True,
                        )
                    )
                    continue
                else:
                    # Circular dependency in singleton/transient - error
                    raise ValueError(
                        f"Circular dependency detected: {provider.name} depends on "
                        f"{type_repr(annotation)}"
                    )

            try:
                dep_provider = self._get_provider(annotation)
            except LookupError:
                # Check if it's a @provided class
                if inspect.isclass(annotation) and is_provided(annotation):
                    provided_scope = annotation.__provided__["scope"]

                    # Auto-register @provided class
                    dep_provider = self._register_provider(
                        annotation,
                        provided_scope,
                        NOT_SET,
                        False,
                    )
                    # Recursively ensure the @provided class is resolved
                    dep_provider = self._ensure_provider_resolved(
                        dep_provider, resolving
                    )
                elif param.has_default:
                    # Has default, can be missing
                    resolved_params.append(param)
                    continue
                else:
                    # Only allow unresolved for scoped providers with FromContext
                    if (
                        provider.scope not in ("singleton", "transient")
                        and from_context
                    ):
                        resolved_params.append(
                            ProviderParameter(
                                name=param.name,
                                annotation=annotation,
                                default=param.default,
                                has_default=param.has_default,
                                provider=None,
                                shared_scope=True,
                            )
                        )
                        continue
                    else:
                        # Required dependency is missing
                        raise LookupError(
                            f"The provider `{provider.name}` depends on "
                            f"`{param.name}` of type "
                            f"`{type_repr(annotation)}`, which has not been "
                            f"registered or set. To resolve this, ensure that "
                            f"`{param.name}` is registered before resolving, "
                            f"or mark it with FromContext[...] if it should be "
                            f"provided via scoped context."
                        ) from None

            # Ensure dependency is also resolved
            dep_provider = self._ensure_provider_resolved(dep_provider, resolving)

            # Validate scope compatibility
            scope_hierarchy = (
                self._scopes.get(provider.scope, ())
                if provider.scope != "transient"
                else ()
            )
            if scope_hierarchy and dep_provider.scope not in scope_hierarchy:
                raise ValueError(
                    f"The provider `{provider.name}` with a `{provider.scope}` scope "
                    f"cannot depend on `{dep_provider.name}` with a "
                    f"`{dep_provider.scope}` scope. Please ensure all providers are "
                    f"registered with matching scopes."
                )

            # Calculate shared_scope
            shared_scope = (
                dep_provider.scope == provider.scope and provider.scope != "transient"
            )

            # Create resolved parameter (use unwrapped annotation)
            resolved_params.append(
                ProviderParameter(
                    name=param.name,
                    annotation=annotation,
                    default=param.default,
                    has_default=param.has_default,
                    provider=dep_provider,
                    shared_scope=shared_scope,
                )
            )

        # Replace provider with resolved version
        resolved_provider = Provider(
            call=provider.call,
            scope=provider.scope,
            interface=provider.interface,
            name=provider.name,
            parameters=tuple(resolved_params),
            is_class=provider.is_class,
            is_coroutine=provider.is_coroutine,
            is_generator=provider.is_generator,
            is_async_generator=provider.is_async_generator,
            is_async=provider.is_async,
            is_resource=provider.is_resource,
        )
        self._providers[provider.interface] = resolved_provider

        return resolved_provider

    def _set_provider(self, provider: Provider) -> None:
        """Set a provider by interface."""
        self._providers[provider.interface] = provider
        if provider.is_resource:
            self._resources[provider.scope].append(provider.interface)

    def _delete_provider(self, provider: Provider) -> None:
        """Delete a provider."""
        if provider.interface in self._providers:
            del self._providers[provider.interface]
        if provider.is_resource:
            self._resources[provider.scope].remove(provider.interface)

    # == Instance Resolution ==

    @overload
    def resolve(self, interface: type[T]) -> T: ...

    @overload
    def resolve(self, interface: T) -> T: ...  # type: ignore

    def resolve(self, interface: type[T]) -> T:
        """Resolve an instance by interface using compiled sync resolver."""
        cached = self._resolver.get_cached(interface, is_async=False)
        if cached is not None:
            return cached.resolve(self)

        provider = self._get_or_register_provider(interface)
        compiled = self._resolver.compile(provider, is_async=False)
        return compiled.resolve(self)

    @overload
    async def aresolve(self, interface: type[T]) -> T: ...

    @overload
    async def aresolve(self, interface: T) -> T: ...

    async def aresolve(self, interface: type[T]) -> T:
        """Resolve an instance by interface asynchronously."""
        cached = self._resolver.get_cached(interface, is_async=True)
        if cached is not None:
            return await cached.resolve(self)

        provider = self._get_or_register_provider(interface)
        compiled = self._resolver.compile(provider, is_async=True)
        return await compiled.resolve(self)

    def create(self, interface: type[T], /, **defaults: Any) -> T:
        """Create an instance by interface."""
        if not defaults:
            cached = self._resolver.get_cached(interface, is_async=False)
            if cached is not None:
                return cached.create(self, None)

        provider = self._get_or_register_provider(interface, defaults)
        compiled = self._resolver.compile(provider, is_async=False)
        return compiled.create(self, defaults or None)

    async def acreate(self, interface: type[T], /, **defaults: Any) -> T:
        """Create an instance by interface asynchronously."""
        if not defaults:
            cached = self._resolver.get_cached(interface, is_async=True)
            if cached is not None:
                return await cached.create(self, None)

        provider = self._get_or_register_provider(interface, defaults)
        compiled = self._resolver.compile(provider, is_async=True)
        return await compiled.create(self, defaults or None)

    def is_resolved(self, interface: Any) -> bool:
        """Check if an instance by interface exists."""
        try:
            provider = self._get_provider(interface)
        except LookupError:
            return False
        if provider.scope == "transient":
            return False
        context = self._get_instance_context(provider.scope)
        return interface in context

    def release(self, interface: Any) -> None:
        """Release an instance by interface."""
        provider = self._get_provider(interface)
        if provider.scope == "transient":
            return None
        context = self._get_instance_context(provider.scope)
        del context[interface]

    def reset(self) -> None:
        """Reset resolved instances."""
        for interface, provider in self._providers.items():
            if provider.scope == "transient":
                continue
            try:
                context = self._get_instance_context(provider.scope)
            except LookupError:
                continue
            del context[interface]

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

    # == Build ==

    def build(self) -> None:
        """Build the container by validating the complete dependency graph."""
        if self._built:
            raise RuntimeError("Container has already been built")

        self._resolve_provider_dependencies()
        self._detect_circular_dependencies()
        self._validate_scope_compatibility()

        self._built = True

    def _resolve_provider_dependencies(self) -> None:
        """Resolve all provider dependencies by filling in provider references."""
        for interface, provider in list(self._providers.items()):
            resolved_params: list[ProviderParameter] = []

            for param in provider.parameters:
                if param.provider is not None:
                    # Already resolved
                    resolved_params.append(param)
                    continue

                # Check if marked with FromContext
                from_context = is_from_context_marker(param.annotation)
                annotation = (
                    unwrap_from_context(param.annotation)
                    if from_context
                    else param.annotation
                )

                # Try to resolve the dependency
                try:
                    dep_provider = self._get_provider(annotation)
                except LookupError:
                    # Check if it's a @provided class
                    if inspect.isclass(annotation) and is_provided(annotation):
                        provided_scope = annotation.__provided__["scope"]

                        # Auto-register @provided class
                        dep_provider = self._register_provider(
                            annotation,
                            provided_scope,
                            NOT_SET,
                            False,
                        )
                    elif param.has_default:
                        # Has default, can be missing
                        resolved_params.append(param)
                        continue
                    else:
                        # Only allow unresolved for scoped providers with FromContext
                        if (
                            provider.scope not in ("singleton", "transient")
                            and from_context
                        ):
                            resolved_params.append(
                                ProviderParameter(
                                    name=param.name,
                                    annotation=annotation,
                                    default=param.default,
                                    has_default=param.has_default,
                                    provider=None,
                                    shared_scope=True,
                                )
                            )
                            continue
                        else:
                            # Required dependency is missing
                            raise LookupError(
                                f"The provider `{provider.name}` depends on "
                                f"`{param.name}` of type "
                                f"`{type_repr(annotation)}`, which has not been "
                                f"registered or set. To resolve this, ensure that "
                                f"`{param.name}` is registered before calling build(), "
                                f"or mark it with FromContext[...] if it should be "
                                f"provided via scoped context."
                            ) from None

                # Calculate shared_scope
                shared_scope = (
                    dep_provider.scope == provider.scope
                    and provider.scope != "transient"
                )

                # Create resolved parameter (use unwrapped annotation)
                resolved_params.append(
                    ProviderParameter(
                        name=param.name,
                        annotation=annotation,
                        default=param.default,
                        has_default=param.has_default,
                        provider=dep_provider,
                        shared_scope=shared_scope,
                    )
                )

            # Replace provider with resolved version
            resolved_provider = Provider(
                call=provider.call,
                scope=provider.scope,
                interface=provider.interface,
                name=provider.name,
                parameters=tuple(resolved_params),
                is_class=provider.is_class,
                is_coroutine=provider.is_coroutine,
                is_generator=provider.is_generator,
                is_async_generator=provider.is_async_generator,
                is_async=provider.is_async,
                is_resource=provider.is_resource,
            )
            self._providers[interface] = resolved_provider

    def _detect_circular_dependencies(self) -> None:
        """Detect circular dependencies in the provider graph."""

        def visit(
            interface: Any,
            provider: Provider,
            path: list[str],
            visited: set[Any],
            in_path: set[Any],
        ) -> None:
            """DFS traversal to detect cycles."""
            if interface in in_path:
                # Found a cycle!
                cycle_start = next(
                    i for i, name in enumerate(path) if name == provider.name
                )
                cycle_path = " -> ".join(path[cycle_start:] + [provider.name])
                raise ValueError(
                    f"Circular dependency detected: {cycle_path}. "
                    f"Please restructure your dependencies to break the cycle."
                )

            if interface in visited:
                return

            visited.add(interface)
            in_path.add(interface)
            path.append(provider.name)

            # Visit dependencies
            for param in provider.parameters:
                # Look up the dependency provider from self._providers instead of
                # using param.provider, which might be stale/unresolved
                if param.annotation in self._providers:
                    dep_provider = self._providers[param.annotation]
                    visit(
                        param.annotation,
                        dep_provider,
                        path,
                        visited,
                        in_path,
                    )

            path.pop()
            in_path.remove(interface)

        visited: set[Any] = set()

        for interface, provider in self._providers.items():
            if interface not in visited:
                visit(interface, provider, [], visited, set())

    def _validate_scope_compatibility(self) -> None:
        """Validate that all dependencies have compatible scopes."""
        for provider in self._providers.values():
            scope = provider.scope

            # Skip validation for transient (can depend on anything)
            if scope == "transient":
                continue

            # Get scope hierarchy for this provider
            scope_hierarchy = (
                self._scopes.get(scope, ()) if scope != "transient" else ()
            )

            # Check each dependency
            for param in provider.parameters:
                if param.provider is None:
                    # Unresolved (allowed for scoped providers)
                    continue

                dep_scope = param.provider.scope

                # Validate scope compatibility
                if scope_hierarchy and dep_scope not in scope_hierarchy:
                    raise ValueError(
                        f"The provider `{provider.name}` with a `{scope}` scope "
                        f"cannot depend on `{param.provider.name}` with a "
                        f"`{dep_scope}` scope. Please ensure all providers are "
                        f"registered with matching scopes."
                    )

    # == Testing / Override Support ==

    @contextlib.contextmanager
    def override(self, interface: Any, instance: Any) -> Iterator[None]:
        """Override a dependency with a specific instance for testing."""
        if not self.has_provider_for(interface):
            raise LookupError(
                f"The provider interface `{type_repr(interface)}` not registered."
            )
        self._resolver.add_override(interface, instance)
        try:
            yield
        finally:
            self._resolver.remove_override(interface)


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
