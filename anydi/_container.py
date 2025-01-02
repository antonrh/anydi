"""AnyDI core implementation module."""

from __future__ import annotations

import contextlib
import functools
import inspect
import types
from collections import defaultdict
from collections.abc import AsyncIterator, Iterable, Iterator, Sequence
from contextvars import ContextVar
from typing import Any, Callable, TypeVar, cast, overload
from weakref import WeakKeyDictionary

from typing_extensions import ParamSpec, Self, final

from ._context import InstanceContext
from ._logger import logger
from ._module import Module, ModuleRegistry
from ._provider import CallableKind, Provider
from ._scanner import Scanner
from ._types import (
    AnyInterface,
    DependencyWrapper,
    Scope,
    is_event_type,
    is_marker,
)
from ._utils import (
    get_full_qualname,
    get_typed_parameters,
    is_async_context_manager,
    is_builtin_type,
    run_async,
)

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
        self._resources: dict[str, list[type[Any]]] = defaultdict(list)
        self._singleton_context = InstanceContext()
        self._request_context_var: ContextVar[InstanceContext | None] = ContextVar(
            "request_context", default=None
        )
        self._override_instances: dict[type[Any], Any] = {}
        self._strict = strict
        self._testing = testing
        self._unresolved_interfaces: set[type[Any]] = set()
        self._inject_cache: WeakKeyDictionary[
            Callable[..., Any], Callable[..., Any]
        ] = WeakKeyDictionary()

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

        # Cleanup instance context
        if provider.scope != "transient":
            try:
                context = self._get_scoped_context(provider.scope)
            except LookupError:
                pass
            else:
                del context[interface]

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
            self._resources[provider.scope].append(provider.interface)

    def _delete_provider(self, provider: Provider) -> None:
        """Delete a provider."""
        if provider.interface in self._providers:
            del self._providers[provider.interface]
        if provider.is_resource:
            self._resources[provider.scope].remove(provider.interface)

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
                # Skip unresolved interfaces in non-strict mode
                if not self.strict and parameter.default is not inspect.Parameter.empty:
                    continue

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
            try:
                sub_provider = self._get_or_register_provider(parameter.annotation)
            except LookupError:
                if not self.strict and parameter.default is not inspect.Parameter.empty:
                    continue
                raise
            scope = sub_provider.scope

            if scope == "transient":
                return "transient"
            scopes.add(scope)

            # If all scopes are found, we can return based on priority order
            if {"transient", "request", "singleton"}.issubset(scopes):
                break  # pragma: no cover

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

    @contextlib.contextmanager
    def request_context(self) -> Iterator[InstanceContext]:
        """Obtain a context manager for the request-scoped context."""
        context = InstanceContext()

        token = self._request_context_var.set(context)

        # Resolve all request resources
        for interface in self._resources.get("request", []):
            if not is_event_type(interface):
                continue
            self.resolve(interface)

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
        for interface in self._resources.get("singleton", []):
            await self.aresolve(interface)

    async def aclose(self) -> None:
        """Close the singleton context asynchronously."""
        await self._singleton_context.aclose()

    @contextlib.asynccontextmanager
    async def arequest_context(self) -> AsyncIterator[InstanceContext]:
        """Obtain an async context manager for the request-scoped context."""
        context = InstanceContext()

        token = self._request_context_var.set(context)

        for interface in self._resources.get("request", []):
            if not is_event_type(interface):
                continue
            await self.aresolve(interface)

        async with context:
            yield context
            self._request_context_var.reset(token)

    def _get_request_context(self) -> InstanceContext:
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
            if provider.scope == "transient":
                continue
            try:
                context = self._get_scoped_context(provider.scope)
            except LookupError:
                continue
            del context[interface]

    @overload
    def resolve(self, interface: type[T]) -> T: ...

    @overload
    def resolve(self, interface: T) -> T: ...

    def resolve(self, interface: type[T]) -> T:
        """Resolve an instance by interface."""
        if interface in self._override_instances:
            return cast(T, self._override_instances[interface])

        provider = self._get_or_register_provider(interface)
        if provider.scope == "transient":
            instance, created = self._create_instance(provider), True
        else:
            context = self._get_scoped_context(provider.scope)
            instance, created = self._get_or_create_instance(provider, context=context)
        if self.testing and created:
            self._patch_test_resolver(instance)
        return cast(T, instance)

    @overload
    async def aresolve(self, interface: type[T]) -> T: ...

    @overload
    async def aresolve(self, interface: T) -> T: ...

    async def aresolve(self, interface: type[T]) -> T:
        """Resolve an instance by interface asynchronously."""
        if interface in self._override_instances:
            return cast(T, self._override_instances[interface])

        provider = self._get_or_register_provider(interface)
        if provider.scope == "transient":
            instance, created = await self._acreate_instance(provider), True
        else:
            context = self._get_scoped_context(provider.scope)
            instance, created = await self._aget_or_create_instance(
                provider, context=context
            )
        if self.testing and created:
            self._patch_test_resolver(instance)
        return cast(T, instance)

    def _get_or_create_instance(
        self, provider: Provider, context: InstanceContext
    ) -> tuple[Any, bool]:
        """Get an instance of a dependency from the scoped context."""
        instance = context.get(provider.interface)
        if instance is None:
            instance = self._create_instance(provider, context=context)
            context.set(provider.interface, instance)
            return instance, True
        return instance, False

    def _create_instance(
        self,
        provider: Provider,
        context: InstanceContext | None = None,
    ) -> Any:
        """Create an instance using the provider."""
        if provider.is_async:
            raise TypeError(
                f"The instance for the provider `{provider}` cannot be created in "
                "synchronous mode."
            )

        args, kwargs = self._get_provided_args(provider, context=context)

        if provider.is_generator:
            if context is None:
                raise ValueError("The context is required for generator providers.")
            cm = contextlib.contextmanager(provider.call)(*args, **kwargs)
            return context.enter(cm)

        instance = provider.call(*args, **kwargs)
        if hasattr(instance, "__enter__") and hasattr(instance, "__exit__"):
            if context is None:
                raise ValueError(
                    "The context is required for context manager providers."
                )
            context.enter(instance)
        return instance

    async def _acreate_instance(  # noqa: C901
        self,
        provider: Provider,
        context: InstanceContext | None = None,
    ) -> Any:
        """Create an instance asynchronously using the provider."""
        args, kwargs = await self._aget_provided_args(provider, context=context)

        if provider.kind == CallableKind.COROUTINE:
            instance = await provider.call(*args, **kwargs)
            if is_async_context_manager(instance):
                if context is None:
                    raise ValueError(
                        "The async stack is required for "
                        "async context manager providers."
                    )
                await context.aenter(instance)
            return instance

        elif provider.kind == CallableKind.ASYNC_GENERATOR:
            if context is None:
                raise ValueError(
                    "The async stack is required for async generator providers."
                )
            cm = contextlib.asynccontextmanager(provider.call)(*args, **kwargs)
            return await context.aenter(cm)

        elif provider.kind == CallableKind.GENERATOR:

            def _create() -> Any:
                if context is None:
                    raise ValueError("The stack is required for generator providers.")
                cm = contextlib.contextmanager(provider.call)(*args, **kwargs)
                return context.enter(cm)

            return await run_async(_create)

        instance = await run_async(provider.call, *args, **kwargs)
        if is_async_context_manager(instance):
            if context is None:
                raise ValueError(
                    "The async stack is required for async context manager providers."
                )
            await context.aenter(instance)
        return instance

    async def _aget_or_create_instance(
        self, provider: Provider, context: InstanceContext
    ) -> tuple[Any, bool]:
        """Get an async instance of a dependency from the scoped context."""
        instance = context.get(provider.interface)
        if instance is None:
            instance = await self._acreate_instance(provider, context=context)
            context.set(provider.interface, instance)
            return instance, True
        return instance, False

    def _get_provided_args(
        self, provider: Provider, context: InstanceContext | None
    ) -> tuple[list[Any], dict[str, Any]]:
        """Retrieve the arguments for a provider."""
        args: list[Any] = []
        kwargs: dict[str, Any] = {}

        for parameter in provider.parameters:
            if parameter.annotation in self._override_instances:
                instance = self._override_instances[parameter.annotation]
            elif context and parameter.annotation in context:
                instance = context[parameter.annotation]
            else:
                try:
                    instance = self._resolve_parameter(provider, parameter)
                except LookupError:
                    if parameter.default is inspect.Parameter.empty:
                        raise
                    instance = parameter.default
                else:
                    if self.testing:
                        instance = DependencyWrapper(
                            interface=parameter.annotation, instance=instance
                        )
            if parameter.kind == parameter.POSITIONAL_ONLY:
                args.append(instance)
            else:
                kwargs[parameter.name] = instance
        return args, kwargs

    async def _aget_provided_args(
        self,
        provider: Provider,
        context: InstanceContext | None,
    ) -> tuple[list[Any], dict[str, Any]]:
        """Asynchronously retrieve the arguments for a provider."""
        args: list[Any] = []
        kwargs: dict[str, Any] = {}

        for parameter in provider.parameters:
            if parameter.annotation in self._override_instances:
                instance = self._override_instances[parameter.annotation]
            elif context and parameter.annotation in context:
                instance = context[parameter.annotation]
            else:
                try:
                    instance = await self._aresolve_parameter(provider, parameter)
                except LookupError:
                    if parameter.default is inspect.Parameter.empty:
                        raise
                    instance = parameter.default
                else:
                    if self.testing:
                        instance = DependencyWrapper(
                            interface=parameter.annotation, instance=instance
                        )
            if parameter.kind == parameter.POSITIONAL_ONLY:
                args.append(instance)
            else:
                kwargs[parameter.name] = instance
        return args, kwargs

    def _resolve_parameter(
        self, provider: Provider, parameter: inspect.Parameter
    ) -> Any:
        self._validate_resolvable_parameter(parameter, call=provider.call)
        return self.resolve(parameter.annotation)

    async def _aresolve_parameter(
        self, provider: Provider, parameter: inspect.Parameter
    ) -> Any:
        self._validate_resolvable_parameter(parameter, call=provider.call)
        return await self.aresolve(parameter.annotation)

    def _validate_resolvable_parameter(
        self, parameter: inspect.Parameter, call: Callable[..., Any]
    ) -> None:
        """Ensure that the specified interface is resolved."""
        if parameter.annotation in self._unresolved_interfaces:
            raise LookupError(
                f"You are attempting to get the parameter `{parameter.name}` with the "
                f"annotation `{get_full_qualname(parameter.annotation)}` as a "
                f"dependency into `{get_full_qualname(call)}` which is not registered "
                "or set in the scoped context."
            )

    def _patch_test_resolver(self, instance: Any) -> None:
        """Patch the test resolver for the instance."""
        if not hasattr(instance, "__dict__"):
            return

        wrapped = {
            name: value.interface
            for name, value in instance.__dict__.items()
            if isinstance(value, DependencyWrapper)
        }

        # Custom resolver function
        def _resolver(_self: Any, _name: str) -> Any:
            if _name in wrapped:
                # Resolve the dependency if it's wrapped
                return self.resolve(wrapped[_name])
            # Fall back to default behavior
            return object.__getattribute__(_self, _name)

        # Apply the patched resolver if wrapped attributes exist
        if wrapped:
            instance.__class__.__getattribute__ = _resolver

    def is_resolved(self, interface: AnyInterface) -> bool:
        """Check if an instance by interface exists."""
        try:
            provider = self._get_provider(interface)
        except LookupError:
            return False
        if provider.scope == "transient":
            return False
        context = self._get_scoped_context(provider.scope)
        return interface in context

    def release(self, interface: AnyInterface) -> None:
        """Release an instance by interface."""
        provider = self._get_provider(interface)
        if provider.scope == "transient":
            return None
        context = self._get_scoped_context(provider.scope)
        del context[interface]

    def _get_scoped_context(self, scope: Scope) -> InstanceContext:
        """Get the instance context for the specified scope."""
        if scope == "singleton":
            return self._singleton_context
        return self._get_request_context()

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
        self, func: Callable[P, T] | None = None
    ) -> Callable[[Callable[P, T]], Callable[P, T]] | Callable[P, T]:
        """Decorator to inject dependencies into a callable."""

        def decorator(
            call: Callable[P, T],
        ) -> Callable[P, T]:
            return self._inject(call)

        if func is None:
            return decorator
        return decorator(func)

    def _inject(
        self,
        call: Callable[P, T],
    ) -> Callable[P, T]:
        """Inject dependencies into a callable."""
        if call in self._inject_cache:
            return cast(Callable[P, T], self._inject_cache[call])

        injected_params = self._get_injected_params(call)

        if inspect.iscoroutinefunction(call):

            @functools.wraps(call)
            async def awrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                for name, annotation in injected_params.items():
                    kwargs[name] = await self.aresolve(annotation)
                return cast(T, await call(*args, **kwargs))

            self._inject_cache[call] = awrapper

            return awrapper  # type: ignore[return-value]

        @functools.wraps(call)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            for name, annotation in injected_params.items():
                kwargs[name] = self.resolve(annotation)
            return call(*args, **kwargs)

        self._inject_cache[call] = wrapper

        return wrapper

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

    def run(self, func: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
        """Run the given function with injected dependencies."""
        return self._inject(func)(*args, **kwargs)

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
