"""AnyDI core implementation module."""

from __future__ import annotations

import contextlib
import inspect
import types
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Iterable, Iterator, Sequence
from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable, TypeVar, cast, overload

from typing_extensions import ParamSpec, Self, final

from ._context import (
    RequestContext,
    ResourceScopedContext,
    ScopedContext,
    SingletonContext,
    TransientContext,
)
from ._logger import logger
from ._module import Module, ModuleRegistry
from ._provider import Provider
from ._scanner import Scanner
from ._types import AnyInterface, Interface, Scope, is_marker
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

        # Components
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
        return self._register_provider(provider, override=override)

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

        self._validate_provider_match_scopes(provider)
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

    def _get_provider(self, interface: AnyInterface) -> Provider:
        """Get provider by interface."""
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

    def _validate_provider_match_scopes(self, provider: Provider) -> None:
        """Validate that the provider and its dependencies have matching scopes."""

        for parameter in provider.parameters:
            annotation = parameter.annotation

            if annotation is inspect._empty:  # noqa
                raise TypeError(
                    f"Missing provider `{provider}` "
                    f"dependency `{parameter.name}` annotation."
                )

            try:
                sub_provider = self._get_or_register_provider(
                    annotation, parent_scope=provider.scope
                )
            except LookupError:
                raise ValueError(
                    f"The provider `{provider}` depends on `{parameter.name}` of type "
                    f"`{get_full_qualname(annotation)}`, which "
                    "has not been registered. To resolve this, ensure that "
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
        return cast(T, scoped_context.get(provider))

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
        return cast(T, await scoped_context.aget(provider))

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
            # Check if the inner callable has already been wrapped
            if hasattr(inner, "__inject_wrapper__"):
                return cast(Callable[P, T | Awaitable[T]], inner.__inject_wrapper__)

            injected_params = self._get_injected_params(inner)

            if inspect.iscoroutinefunction(inner):

                @wraps(inner)
                async def awrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                    for name, annotation in injected_params.items():
                        kwargs[name] = await self.aresolve(annotation)
                    return cast(T, await inner(*args, **kwargs))

                inner.__inject_wrapper__ = awrapper  # type: ignore[attr-defined]

                return awrapper

            @wraps(inner)
            def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                for name, annotation in injected_params.items():
                    kwargs[name] = self.resolve(annotation)
                return cast(T, inner(*args, **kwargs))

            inner.__inject_wrapper__ = wrapper  # type: ignore[attr-defined]

            return wrapper

        if func is None:
            return decorator
        return decorator(func)

    def run(self, func: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
        """Run the given function with injected dependencies."""
        return self.inject(func)(*args, **kwargs)

    def scan(
        self,
        /,
        packages: types.ModuleType | str | Iterable[types.ModuleType | str],
        *,
        tags: Iterable[str] | None = None,
    ) -> None:
        """Scan packages or modules for decorated members and inject dependencies."""
        self._scanner.scan(packages, tags=tags)

    def _get_injected_params(self, call: Callable[..., Any]) -> dict[str, Any]:
        """Get the injected parameters of a callable object."""
        injected_params = {}
        for parameter in get_typed_parameters(call):
            if not is_marker(parameter.default):
                continue
            try:
                self._validate_injected_parameter(call, parameter)
            except LookupError as exc:
                if not self.strict:
                    logger.debug(
                        f"Cannot validate the `{get_full_qualname(call)}` parameter "
                        f"`{parameter.name}` with an annotation of "
                        f"`{get_full_qualname(parameter.annotation)} due to being "
                        "in non-strict mode. It will be validated at the first call."
                    )
                else:
                    raise exc
            injected_params[parameter.name] = parameter.annotation
        return injected_params

    def _validate_injected_parameter(
        self, call: Callable[..., Any], parameter: inspect.Parameter
    ) -> None:
        """Validate an injected parameter."""
        if parameter.annotation is inspect.Parameter.empty:
            raise TypeError(
                f"Missing `{get_full_qualname(call)}` parameter "
                f"`{parameter.name}` annotation."
            )

        if not self.is_registered(parameter.annotation):
            raise LookupError(
                f"`{get_full_qualname(call)}` has an unknown dependency parameter "
                f"`{parameter.name}` with an annotation of "
                f"`{get_full_qualname(parameter.annotation)}`."
            )


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
