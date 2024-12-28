"""AnyDI core implementation module."""

from __future__ import annotations

import contextlib
import inspect
import types
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Iterable, Iterator, Sequence
from contextvars import ContextVar
from typing import Any, Callable, TypeVar, Union, cast, get_args, overload

from typing_extensions import ParamSpec, Self, final, get_origin, is_protocol

from ._context import (
    RequestContext,
    ResourceScopedContext,
    ScopedContext,
    SingletonContext,
    TransientContext,
)
from ._injector import Injector
from ._module import Module, ModuleRegistry
from ._provider import Provider
from ._scanner import Scanner
from ._types import AnyInterface, Interface, Scope
from ._utils import get_full_qualname, get_typed_parameters, is_builtin_type

T = TypeVar("T", bound=Any)
P = ParamSpec("P")

ALLOWED_SCOPES: dict[Scope, list[Scope]] = {
    "singleton": ["singleton"],
    "request": ["request", "singleton"],
    "transient": ["transient", "singleton", "request"],
}


@final
class Container:
    """AnyDI is a dependency injection container."""

    def __init__(
        self,
        *,
        providers: Sequence[Provider] | None = None,
        modules: Sequence[Module | type[Module] | Callable[[Container], None] | str]
        | None = None,
        strict: bool = False,
        testing: bool = False,
    ) -> None:
        self._providers: dict[type[Any], Provider] = {}
        self._resource_cache: dict[Scope, list[type[Any]]] = defaultdict(list)
        self._singleton_context = SingletonContext(self)
        self._transient_context = TransientContext(self)
        self._request_context_var: ContextVar[RequestContext | None] = ContextVar(
            "request_context", default=None
        )
        self._override_instances: dict[type[Any], Any] = {}
        self._strict = strict
        self._testing = testing
        self._unresolved_interfaces: set[type[Any]] = set()
        self._aliases: dict[type[Any], type[Any]] = {}

        # Components
        self._injector = Injector(self)
        self._modules = ModuleRegistry(self)
        self._scanner = Scanner(self)

        # Register providers
        providers = providers or []
        for provider in providers:
            self._register_provider(provider)

        # Register modules
        modules = modules or []
        for module in modules:
            self.register_module(module)

    @property
    def strict(self) -> bool:
        """Check if strict mode is enabled."""
        return self._strict

    @property
    def testing(self) -> bool:
        """Check if testing mode is enabled."""
        return self._testing

    @property
    def providers(self) -> dict[type[Any], Provider]:
        """Get the registered providers."""
        return self._providers

    def is_registered(self, interface: AnyInterface) -> bool:
        """Check if a provider is registered for the specified interface."""
        return interface in self._providers

    def register(
        self,
        interface: AnyInterface,
        call: Callable[..., Any],
        *,
        scope: Scope,
        override: bool = False,
    ) -> Provider:
        """Register a provider for the specified interface."""
        provider = Provider(call=call, scope=scope, interface=interface)
        self._register_provider(provider, override=override)
        for alias in provider.aliases:
            self._alias(provider.interface, alias)
        return provider

    def _register_provider(
        self, provider: Provider, *, override: bool = False
    ) -> Provider:
        """Register a provider."""
        if provider.interface in self._providers:
            if override:
                self._set_provider(provider)
                return provider

            raise LookupError(
                f"The provider interface `{get_full_qualname(provider.interface)}` "
                "already registered."
            )

        self._validate_sub_providers(provider)
        self._set_provider(provider)
        return provider

    def unregister(self, interface: AnyInterface) -> None:
        """Unregister a provider by interface."""
        if not self.is_registered(interface):
            raise LookupError(
                "The provider interface "
                f"`{get_full_qualname(interface)}` not registered."
            )

        provider = self._get_provider(interface)

        # Cleanup scoped context instance
        try:
            scoped_context = self._get_scoped_context(provider.scope)
        except LookupError:
            pass
        else:
            if isinstance(scoped_context, ResourceScopedContext):
                scoped_context.delete(interface)

        # Cleanup provider references
        self._delete_provider(provider)

    def alias(self, interface: AnyInterface, alias: AnyInterface) -> None:
        """Add an alias for the specified interface."""
        if get_origin(alias) is Union:
            for sub_alias in get_args(alias):
                self._alias(interface, sub_alias)
            return None
        self._alias(interface, alias)

    def _alias(self, interface: AnyInterface, alias: AnyInterface) -> None:
        """Add an alias for the specified interface."""
        if alias in self._aliases:
            raise LookupError(
                f"The interface `{get_full_qualname(alias)}` is already aliased."
            )
        provider = self._get_or_register_provider(interface)
        self._aliases[alias] = interface
        scoped_context = self._get_scoped_context(provider.scope)
        scoped_context.alias(interface, alias)

    def _get_provider(self, interface: AnyInterface) -> Provider:
        """Get provider by interface."""
        interface = self._aliases.get(interface, interface)
        try:
            return self._providers[interface]
        except KeyError as exc:
            raise LookupError(
                f"The provider interface for `{get_full_qualname(interface)}` has "
                "not been registered. Please ensure that the provider interface is "
                "properly registered before attempting to use it."
            ) from exc

    def _get_or_register_provider(
        self, interface: AnyInterface, parent_scope: Scope | None = None
    ) -> Provider:
        """Get or register a provider by interface."""
        try:
            return self._get_provider(interface)
        except LookupError:
            if (
                not self.strict
                and inspect.isclass(interface)
                and not inspect.isabstract(interface)
                and not is_protocol(interface)
                and not is_builtin_type(interface)
                and interface is not inspect.Parameter.empty
            ):
                # Try to get defined scope
                scope = getattr(interface, "__scope__", parent_scope)
                # Try to detect scope
                if scope is None:
                    scope = self._detect_scope(interface)
                return self.register(interface, interface, scope=scope or "transient")
            raise

    def _set_provider(self, provider: Provider) -> None:
        """Set a provider by interface."""
        self._providers[provider.interface] = provider
        if provider.is_resource:
            self._resource_cache[provider.scope].append(provider.interface)

    def _delete_provider(self, provider: Provider) -> None:
        """Delete a provider."""
        if provider.interface in self._providers:
            del self._providers[provider.interface]
        if provider.is_resource:
            self._resource_cache[provider.scope].remove(provider.interface)

    def _validate_sub_providers(self, provider: Provider) -> None:
        """Validate the sub-providers of a provider."""

        for parameter in provider.parameters:
            annotation = parameter.annotation

            if annotation is inspect.Parameter.empty:
                raise TypeError(
                    f"Missing provider `{provider}` "
                    f"dependency `{parameter.name}` annotation."
                )

            try:
                sub_provider = self._get_or_register_provider(
                    annotation, parent_scope=provider.scope
                )
            except LookupError:
                if provider.scope not in {"singleton", "transient"}:
                    self._unresolved_interfaces.add(provider.interface)
                    continue
                raise ValueError(
                    f"The provider `{provider}` depends on `{parameter.name}` of type "
                    f"`{get_full_qualname(annotation)}`, which "
                    "has not been registered or set. To resolve this, ensure that "
                    f"`{parameter.name}` is registered before attempting to use it."
                ) from None

            # Check scope compatibility
            if sub_provider.scope not in ALLOWED_SCOPES.get(provider.scope, []):
                raise ValueError(
                    f"The provider `{provider}` with a `{provider.scope}` scope cannot "
                    f"depend on `{sub_provider}` with a `{sub_provider.scope}` scope. "
                    "Please ensure all providers are registered with matching scopes."
                )

    def _detect_scope(self, call: Callable[..., Any]) -> Scope | None:
        """Detect the scope for a callable."""
        scopes = set()

        for parameter in get_typed_parameters(call):
            sub_provider = self._get_or_register_provider(parameter.annotation)
            scope = sub_provider.scope

            if scope == "transient":
                return "transient"
            scopes.add(scope)

            # If all scopes are found, we can return based on priority order
            if {"transient", "request", "singleton"}.issubset(scopes):
                break

        # Determine scope based on priority
        if "request" in scopes:
            return "request"
        if "singleton" in scopes:
            return "singleton"

        return None

    def register_module(
        self, module: Module | type[Module] | Callable[[Container], None] | str
    ) -> None:
        """Register a module as a callable, module type, or module instance."""
        self._modules.register(module)

    def __enter__(self) -> Self:
        """Enter the singleton context."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> bool:
        """Exit the singleton context."""
        return self._singleton_context.__exit__(exc_type, exc_val, exc_tb)

    def start(self) -> None:
        """Start the singleton context."""
        self._singleton_context.start()

    def close(self) -> None:
        """Close the singleton context."""
        self._singleton_context.close()

    @contextlib.contextmanager
    def request_context(self) -> Iterator[RequestContext]:
        """Obtain a context manager for the request-scoped context."""
        context = RequestContext(self)
        token = self._request_context_var.set(context)
        with context:
            yield context
            self._request_context_var.reset(token)

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
        await self._singleton_context.astart()

    async def aclose(self) -> None:
        """Close the singleton context asynchronously."""
        await self._singleton_context.aclose()

    @contextlib.asynccontextmanager
    async def arequest_context(self) -> AsyncIterator[RequestContext]:
        """Obtain an async context manager for the request-scoped context."""
        context = RequestContext(self)
        token = self._request_context_var.set(context)
        async with context:
            yield context
            self._request_context_var.reset(token)

    def _get_request_context(self) -> RequestContext:
        """Get the current request context."""
        request_context = self._request_context_var.get()
        if request_context is None:
            raise LookupError(
                "The request context has not been started. Please ensure that "
                "the request context is properly initialized before attempting "
                "to use it."
            )
        return request_context

    def reset(self) -> None:
        """Reset resolved instances."""
        for interface, provider in self._providers.items():
            try:
                scoped_context = self._get_scoped_context(provider.scope)
            except LookupError:
                continue
            if isinstance(scoped_context, ResourceScopedContext):
                scoped_context.delete(interface)

    @overload
    def resolve(self, interface: Interface[T]) -> T: ...

    @overload
    def resolve(self, interface: T) -> T: ...

    def resolve(self, interface: Interface[T]) -> T:
        """Resolve an instance by interface."""
        if interface in self._override_instances:
            return cast(T, self._override_instances[interface])

        provider = self._get_or_register_provider(interface)
        scoped_context = self._get_scoped_context(provider.scope)
        instance, created = scoped_context.get_or_create(provider)
        if self.testing and created:
            self._patch_for_testing(instance)
        return cast(T, instance)

    def _patch_for_testing(self, instance: Any) -> None:
        """Patch the instance class for testing."""

        def _resolver(_self: Any, name: str) -> Any:
            if not name.startswith("__"):
                # Get annotations from the constructor only once
                if not hasattr(_self, "__cached_annotations__"):
                    constructor = object.__getattribute__(_self, "__init__")
                    _self.__cached_annotations__ = {
                        parameter.name: parameter.annotation
                        for parameter in get_typed_parameters(constructor)
                        if parameter.annotation is not inspect.Parameter.empty
                    }
                _annotations = _self.__cached_annotations__

                if name in _annotations:
                    return self.resolve(_annotations[name])

            return object.__getattribute__(_self, name)

        if hasattr(instance, "__class__") and not is_builtin_type(instance.__class__):
            instance.__class__.__getattribute__ = _resolver

    @overload
    async def aresolve(self, interface: Interface[T]) -> T: ...

    @overload
    async def aresolve(self, interface: T) -> T: ...

    async def aresolve(self, interface: Interface[T]) -> T:
        """Resolve an instance by interface asynchronously."""
        if interface in self._override_instances:
            return cast(T, self._override_instances[interface])

        provider = self._get_or_register_provider(interface)
        scoped_context = self._get_scoped_context(provider.scope)
        instance, created = await scoped_context.aget_or_create(provider)
        if self.testing and created:
            self._patch_for_testing(instance)
        return cast(T, instance)

    def is_resolved(self, interface: AnyInterface) -> bool:
        """Check if an instance by interface exists."""
        try:
            provider = self._get_provider(interface)
        except LookupError:
            pass
        else:
            scoped_context = self._get_scoped_context(provider.scope)
            if isinstance(scoped_context, ResourceScopedContext):
                return scoped_context.has(interface)
        return False

    def release(self, interface: AnyInterface) -> None:
        """Release an instance by interface."""
        provider = self._get_provider(interface)
        scoped_context = self._get_scoped_context(provider.scope)
        if isinstance(scoped_context, ResourceScopedContext):
            scoped_context.delete(interface)

    def _get_scoped_context(self, scope: Scope) -> ScopedContext:
        """Get the scoped context based on the specified scope."""
        if scope == "singleton":
            return self._singleton_context
        elif scope == "request":
            request_context = self._get_request_context()
            return request_context
        return self._transient_context

    @contextlib.contextmanager
    def override(self, interface: AnyInterface, instance: Any) -> Iterator[None]:
        """
        Override the provider for the specified interface with a specific instance.
        """
        if not self.is_registered(interface) and self.strict:
            raise LookupError(
                f"The provider interface `{get_full_qualname(interface)}` "
                "not registered."
            )
        self._override_instances[interface] = instance
        yield
        del self._override_instances[interface]

    def provider(
        self, *, scope: Scope, override: bool = False
    ) -> Callable[[Callable[P, T]], Callable[P, T]]:
        """Decorator to register a provider function with the specified scope."""

        def decorator(call: Callable[P, T]) -> Callable[P, T]:
            provider = Provider(call=call, scope=scope)
            self._register_provider(provider, override=override)
            for alias in provider.aliases:
                self._alias(provider.interface, alias)
            return call

        return decorator

    @overload
    def inject(self, func: Callable[P, T]) -> Callable[P, T]: ...

    @overload
    def inject(self) -> Callable[[Callable[P, T]], Callable[P, T]]: ...

    def inject(
        self, func: Callable[P, T | Awaitable[T]] | None = None
    ) -> (
        Callable[[Callable[P, T | Awaitable[T]]], Callable[P, T | Awaitable[T]]]
        | Callable[P, T | Awaitable[T]]
    ):
        """Decorator to inject dependencies into a callable."""

        def decorator(
            inner: Callable[P, T | Awaitable[T]],
        ) -> Callable[P, T | Awaitable[T]]:
            return self._injector.inject(inner)

        if func is None:
            return decorator
        return decorator(func)

    def run(self, func: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
        """Run the given function with injected dependencies."""
        return cast(T, self._injector.inject(func)(*args, **kwargs))

    def scan(
        self,
        /,
        packages: types.ModuleType | str | Iterable[types.ModuleType | str],
        *,
        tags: Iterable[str] | None = None,
    ) -> None:
        """Scan packages or modules for decorated members and inject dependencies."""
        self._scanner.scan(packages, tags=tags)


def transient(target: T) -> T:
    """Decorator for marking a class as transient scope."""
    setattr(target, "__scope__", "transient")
    return target


def request(target: T) -> T:
    """Decorator for marking a class as request scope."""
    setattr(target, "__scope__", "request")
    return target


def singleton(target: T) -> T:
    """Decorator for marking a class as singleton scope."""
    setattr(target, "__scope__", "singleton")
    return target
