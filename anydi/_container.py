"""AnyDI core implementation module."""

from __future__ import annotations

import contextlib
import functools
import importlib
import inspect
import logging
import pkgutil
import threading
import types
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator, Iterable, Iterator, Sequence
from contextvars import ContextVar
from types import ModuleType
from typing import Annotated, Any, Callable, TypeVar, Union, cast, overload

from typing_extensions import Concatenate, ParamSpec, Self, final, get_args, get_origin

from ._context import InstanceContext
from ._types import (
    NOT_SET,
    AnyInterface,
    Event,
    InjectableDecoratorArgs,
    InstanceProxy,
    Provider,
    ProviderArgs,
    ProviderDecoratorArgs,
    ProviderKind,
    ScannedDependency,
    Scope,
    is_event_type,
    is_marker,
)
from ._utils import (
    AsyncRLock,
    get_full_qualname,
    get_typed_annotation,
    get_typed_parameters,
    import_string,
    is_async_context_manager,
    is_builtin_type,
    is_context_manager,
    run_async,
)

try:
    from types import NoneType
except ImportError:
    NoneType = type(None)  # type: ignore[misc]


T = TypeVar("T", bound=Any)
M = TypeVar("M", bound="Module")
P = ParamSpec("P")

ALLOWED_SCOPES: dict[Scope, list[Scope]] = {
    "singleton": ["singleton"],
    "request": ["request", "singleton"],
    "transient": ["transient", "request", "singleton"],
}


class ModuleMeta(type):
    """A metaclass used for the Module base class."""

    def __new__(cls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]) -> Any:
        attrs["providers"] = [
            (name, getattr(value, "__provider__"))
            for name, value in attrs.items()
            if hasattr(value, "__provider__")
        ]
        return super().__new__(cls, name, bases, attrs)


class Module(metaclass=ModuleMeta):
    """A base class for defining AnyDI modules."""

    providers: list[tuple[str, ProviderDecoratorArgs]]

    def configure(self, container: Container) -> None:
        """Configure the AnyDI container with providers and their dependencies."""


@final
class Container:
    """AnyDI is a dependency injection container."""

    def __init__(
        self,
        *,
        providers: Sequence[ProviderArgs] | None = None,
        modules: Sequence[Module | type[Module] | Callable[[Container], None] | str]
        | None = None,
        strict: bool = False,
        default_scope: Scope = "transient",
        testing: bool = False,
        logger: logging.Logger | None = None,
    ) -> None:
        self._providers: dict[type[Any], Provider] = {}
        self._strict = strict
        self._default_scope = default_scope
        self._testing = testing
        self._logger = logger or logging.getLogger(__name__)
        self._resources: dict[str, list[type[Any]]] = defaultdict(list)
        self._singleton_context = InstanceContext()
        self._singleton_lock = threading.RLock()
        self._singleton_async_lock = AsyncRLock()
        self._request_context_var: ContextVar[InstanceContext | None] = ContextVar(
            "request_context", default=None
        )
        self._override_instances: dict[type[Any], Any] = {}
        self._unresolved_interfaces: set[type[Any]] = set()
        self._inject_cache: dict[Callable[..., Any], Callable[..., Any]] = {}

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

    ############################
    # Properties
    ############################

    @property
    def strict(self) -> bool:
        """Check if strict mode is enabled."""
        return self._strict

    @property
    def default_scope(self) -> Scope:
        """Get the default scope."""
        return self._default_scope

    @property
    def testing(self) -> bool:
        """Check if testing mode is enabled."""
        return self._testing

    @property
    def providers(self) -> dict[type[Any], Provider]:
        """Get the registered providers."""
        return self._providers

    @property
    def logger(self) -> logging.Logger:
        """Get the logger instance."""
        return self._logger

    ############################
    # Lifespan/Context Methods
    ############################

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

    def _get_scoped_context(self, scope: Scope) -> InstanceContext:
        """Get the instance context for the specified scope."""
        if scope == "singleton":
            return self._singleton_context
        return self._get_request_context()

    ############################
    # Provider Methods
    ############################

    def register(
        self,
        interface: AnyInterface,
        call: Callable[..., Any],
        *,
        scope: Scope,
        override: bool = False,
    ) -> Provider:
        """Register a provider for the specified interface."""
        return self._register_provider(call, scope, interface, override)

    def is_registered(self, interface: AnyInterface) -> bool:
        """Check if a provider is registered for the specified interface."""
        return interface in self._providers

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
        scope: Scope | None,
        interface: Any = NOT_SET,
        override: bool = False,
        /,
        **defaults: Any,
    ) -> Provider:
        """Register a provider with the specified scope."""
        name = get_full_qualname(call)
        kind = ProviderKind.from_call(call)
        detected_scope = scope

        # Validate scope if it provided
        if scope:
            self._validate_provider_scope(scope, name, kind)

        # Get the signature
        globalns = getattr(call, "__globals__", {})
        module = getattr(call, "__module__", None)
        signature = inspect.signature(call, globals=globalns)

        # Detect the interface
        if interface is NOT_SET:
            if kind == ProviderKind.CLASS:
                interface = call
            else:
                interface = signature.return_annotation
                if interface is inspect.Signature.empty:
                    interface = None
                else:
                    interface = get_typed_annotation(interface, globalns, module)

        # If the callable is an iterator, return the actual type
        iterator_types = {Iterator, AsyncIterator}
        if interface in iterator_types or get_origin(interface) in iterator_types:
            if args := get_args(interface):
                interface = args[0]
                # If the callable is a generator, return the resource type
                if interface in {None, NoneType}:
                    interface = type(f"Event_{uuid.uuid4().hex}", (Event,), {})
            else:
                raise TypeError(
                    f"Cannot use `{name}` resource type annotation "
                    "without actual type argument."
                )

        # None interface is not allowed
        if interface in {None, NoneType}:
            raise TypeError(f"Missing `{name}` provider return annotation.")

        # Check for existing provider
        if interface in self._providers and not override:
            raise LookupError(
                f"The provider interface `{get_full_qualname(interface)}` "
                "already registered."
            )

        unresolved_parameter = None
        parameters = []
        scopes = {}

        for parameter in signature.parameters.values():
            if parameter.annotation is inspect.Parameter.empty:
                raise TypeError(
                    f"Missing provider `{name}` "
                    f"dependency `{parameter.name}` annotation."
                )
            if parameter.kind == inspect.Parameter.POSITIONAL_ONLY:
                raise TypeError(
                    "Positional-only parameters "
                    f"are not allowed in the provider `{name}`."
                )

            parameter = parameter.replace(
                annotation=get_typed_annotation(parameter.annotation, globalns, module)
            )

            try:
                sub_provider = self._get_or_register_provider(
                    parameter.annotation, scope
                )
            except LookupError:
                if self._parameter_has_default(parameter, **defaults):
                    continue
                unresolved_parameter = parameter
                continue

            # Store first provider for each scope
            if sub_provider.scope not in scopes:
                scopes[sub_provider.scope] = sub_provider

            parameters.append(parameter)

        # Set detected scope
        if detected_scope is None:
            if "transient" in scopes:
                detected_scope = "transient"
            elif "request" in scopes:
                detected_scope = "request"
            elif "singleton" in scopes:
                detected_scope = "singleton"
            else:
                detected_scope = self.default_scope

        # Validate the provider scope after detection
        if scope is None:
            self._validate_provider_scope(detected_scope, name, kind)

        # Check for unresolved parameters
        if unresolved_parameter:
            if detected_scope not in {"singleton", "transient"}:
                self._unresolved_interfaces.add(interface)
            else:
                raise LookupError(
                    f"The provider `{name}` depends on `{unresolved_parameter.name}` "
                    f"of type `{get_full_qualname(unresolved_parameter.annotation)}`, "
                    "which has not been registered or set. To resolve this, ensure "
                    f"that `{unresolved_parameter.name}` is registered before "
                    f"attempting to use it."
                ) from None

        # Check scope compatibility
        for sub_provider in scopes.values():
            if sub_provider.scope not in ALLOWED_SCOPES.get(detected_scope, []):
                raise ValueError(
                    f"The provider `{name}` with a `{detected_scope}` scope cannot "
                    f"depend on `{sub_provider}` with a `{sub_provider.scope}` scope. "
                    "Please ensure all providers are registered with matching scopes."
                )

        provider = Provider(
            call=call,
            scope=detected_scope,
            interface=interface,
            name=name,
            kind=kind,
            parameters=parameters,
        )

        self._set_provider(provider)
        return provider

    def _validate_provider_scope(
        self, scope: Scope, name: str, kind: ProviderKind
    ) -> None:
        """Validate the provider scope."""
        if scope not in (allowed_scopes := get_args(Scope)):
            raise ValueError(
                f"The provider `{name}` scope is invalid. Only the following "
                f"scopes are supported: {', '.join(allowed_scopes)}. "
                "Please use one of the supported scopes when registering a provider."
            )
        if (
            kind in {ProviderKind.GENERATOR, ProviderKind.ASYNC_GENERATOR}
            and scope == "transient"
        ):
            raise TypeError(
                f"The resource provider `{name}` is attempting to register "
                "with a transient scope, which is not allowed."
            )

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
        self, interface: AnyInterface, parent_scope: Scope | None, /, **defaults: Any
    ) -> Provider:
        """Get or register a provider by interface."""
        try:
            return self._get_provider(interface)
        except LookupError:
            if self.strict or interface is inspect.Parameter.empty:
                raise
            if get_origin(interface) is Annotated and (args := get_args(interface)):
                call = args[0]
            else:
                call = interface
            if inspect.isclass(call) and not is_builtin_type(call):
                # Try to get defined scope
                scope = getattr(interface, "__scope__", parent_scope)
                return self._register_provider(call, scope, interface, **defaults)
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

    def _parameter_has_default(
        self, parameter: inspect.Parameter, /, **defaults: Any
    ) -> bool:
        return (defaults and parameter.name in defaults) or (
            not self.strict and parameter.default is not inspect.Parameter.empty
        )

    ############################
    # Instance Methods
    ############################

    @overload
    def resolve(self, interface: type[T]) -> T: ...

    @overload
    def resolve(self, interface: T) -> T: ...

    def resolve(self, interface: type[T]) -> T:
        """Resolve an instance by interface."""
        return self._resolve_or_create(interface, False)

    @overload
    async def aresolve(self, interface: type[T]) -> T: ...

    @overload
    async def aresolve(self, interface: T) -> T: ...

    async def aresolve(self, interface: type[T]) -> T:
        """Resolve an instance by interface asynchronously."""
        return await self._aresolve_or_create(interface, False)

    def create(self, interface: type[T], /, **defaults: Any) -> T:
        """Create an instance by interface."""
        return self._resolve_or_create(interface, True, **defaults)

    async def acreate(self, interface: type[T], /, **defaults: Any) -> T:
        """Create an instance by interface asynchronously."""
        return await self._aresolve_or_create(interface, True, **defaults)

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

    def _resolve_or_create(
        self, interface: type[T], create: bool, /, **defaults: Any
    ) -> T:
        """Internal method to handle instance resolution and creation."""
        provider = self._get_or_register_provider(interface, None, **defaults)
        if provider.scope == "transient":
            instance = self._create_instance(provider, None, **defaults)
        else:
            context = self._get_scoped_context(provider.scope)
            if provider.scope == "singleton":
                with self._singleton_lock:
                    instance = (
                        self._get_or_create_instance(provider, context)
                        if not create
                        else self._create_instance(provider, context, **defaults)
                    )
            else:
                instance = (
                    self._get_or_create_instance(provider, context)
                    if not create
                    else self._create_instance(provider, context, **defaults)
                )

        if self.testing:
            instance = self._patch_test_resolver(provider.interface, instance)

        return cast(T, instance)

    async def _aresolve_or_create(
        self, interface: type[T], create: bool, /, **defaults: Any
    ) -> T:
        """Internal method to handle instance resolution and creation asynchronously."""
        provider = self._get_or_register_provider(interface, None, **defaults)
        if provider.scope == "transient":
            instance = await self._acreate_instance(provider, None, **defaults)
        else:
            context = self._get_scoped_context(provider.scope)
            if provider.scope == "singleton":
                async with self._singleton_async_lock:
                    instance = (
                        await self._aget_or_create_instance(provider, context)
                        if not create
                        else await self._acreate_instance(provider, context, **defaults)
                    )
            else:
                instance = (
                    await self._aget_or_create_instance(provider, context)
                    if not create
                    else await self._acreate_instance(provider, context, **defaults)
                )

        if self.testing:
            instance = self._patch_test_resolver(provider.interface, instance)

        return cast(T, instance)

    def _get_or_create_instance(
        self, provider: Provider, context: InstanceContext
    ) -> Any:
        """Get an instance of a dependency from the scoped context."""
        instance = context.get(provider.interface)
        if instance is None:
            instance = self._create_instance(provider, context)
            context.set(provider.interface, instance)
            return instance
        return instance

    async def _aget_or_create_instance(
        self, provider: Provider, context: InstanceContext
    ) -> Any:
        """Get an async instance of a dependency from the scoped context."""
        instance = context.get(provider.interface)
        if instance is None:
            instance = await self._acreate_instance(provider, context)
            context.set(provider.interface, instance)
            return instance
        return instance

    def _create_instance(
        self, provider: Provider, context: InstanceContext | None, /, **defaults: Any
    ) -> Any:
        """Create an instance using the provider."""
        if provider.is_async:
            raise TypeError(
                f"The instance for the provider `{provider}` cannot be created in "
                "synchronous mode."
            )

        provider_kwargs = self._get_provided_kwargs(provider, context, **defaults)

        if provider.is_generator:
            if context is None:
                raise ValueError("The context is required for generator providers.")
            cm = contextlib.contextmanager(provider.call)(**provider_kwargs)
            return context.enter(cm)

        instance = provider.call(**provider_kwargs)
        if context is not None and provider.is_class and is_context_manager(instance):
            context.enter(instance)
        return instance

    async def _acreate_instance(
        self, provider: Provider, context: InstanceContext | None, /, **defaults: Any
    ) -> Any:
        """Create an instance asynchronously using the provider."""
        provider_kwargs = await self._aget_provided_kwargs(
            provider, context, **defaults
        )

        if provider.is_coroutine:
            return await provider.call(**provider_kwargs)

        if provider.is_async_generator:
            if context is None:
                raise ValueError(
                    "The async stack is required for async generator providers."
                )
            cm = contextlib.asynccontextmanager(provider.call)(**provider_kwargs)
            return await context.aenter(cm)

        if provider.is_generator:

            def _create() -> Any:
                if context is None:
                    raise ValueError("The stack is required for generator providers.")
                cm = contextlib.contextmanager(provider.call)(**provider_kwargs)
                return context.enter(cm)

            return await run_async(_create)

        instance = await run_async(provider.call, **provider_kwargs)
        if (
            context is not None
            and provider.is_class
            and is_async_context_manager(instance)
        ):
            await context.aenter(instance)
        return instance

    def _get_provided_kwargs(
        self, provider: Provider, context: InstanceContext | None, /, **defaults: Any
    ) -> dict[str, Any]:
        """Retrieve the arguments for a provider."""
        provided_kwargs = {}
        for parameter in provider.parameters:
            instance = self._get_provider_instance(
                provider, parameter, context, **defaults
            )
            provided_kwargs[parameter.name] = instance
        return {**defaults, **provided_kwargs}

    def _get_provider_instance(
        self,
        provider: Provider,
        parameter: inspect.Parameter,
        context: InstanceContext | None,
        /,
        **defaults: Any,
    ) -> Any:
        """Retrieve an instance of a dependency from the scoped context."""

        # Try to get instance from defaults
        if parameter.name in defaults:
            return defaults[parameter.name]

        # Try to get instance from context
        elif context and parameter.annotation in context:
            instance = context[parameter.annotation]

        # Resolve new instance
        else:
            try:
                instance = self._resolve_parameter(provider, parameter)
            except LookupError:
                if parameter.default is inspect.Parameter.empty:
                    raise
                return parameter.default

        # Wrap the instance in a proxy for testing
        if self.testing:
            return InstanceProxy(instance, interface=parameter.annotation)
        return instance

    async def _aget_provided_kwargs(
        self, provider: Provider, context: InstanceContext | None, /, **defaults: Any
    ) -> dict[str, Any]:
        """Asynchronously retrieve the arguments for a provider."""
        provided_kwargs = {}
        for parameter in provider.parameters:
            instance = await self._aget_provider_instance(
                provider, parameter, context, **defaults
            )
            provided_kwargs[parameter.name] = instance
        return {**defaults, **provided_kwargs}

    async def _aget_provider_instance(
        self,
        provider: Provider,
        parameter: inspect.Parameter,
        context: InstanceContext | None,
        /,
        **defaults: Any,
    ) -> Any:
        """Asynchronously retrieve an instance of a dependency from the context."""

        # Try to get instance from defaults
        if parameter.name in defaults:
            return defaults[parameter.name]

        # Try to get instance from context
        elif context and parameter.annotation in context:
            instance = context[parameter.annotation]

        # Resolve new instance
        else:
            try:
                instance = await self._aresolve_parameter(provider, parameter)
            except LookupError:
                if parameter.default is inspect.Parameter.empty:
                    raise
                return parameter.default

        # Wrap the instance in a proxy for testing
        if self.testing:
            return InstanceProxy(instance, interface=parameter.annotation)
        return instance

    def _resolve_parameter(
        self, provider: Provider, parameter: inspect.Parameter
    ) -> Any:
        self._validate_resolvable_parameter(provider, parameter)
        return self.resolve(parameter.annotation)

    async def _aresolve_parameter(
        self, provider: Provider, parameter: inspect.Parameter
    ) -> Any:
        self._validate_resolvable_parameter(provider, parameter)
        return await self.aresolve(parameter.annotation)

    def _validate_resolvable_parameter(
        self, provider: Provider, parameter: inspect.Parameter
    ) -> None:
        """Ensure that the specified interface is resolved."""
        if parameter.annotation in self._unresolved_interfaces:
            raise LookupError(
                f"You are attempting to get the parameter `{parameter.name}` with the "
                f"annotation `{get_full_qualname(parameter.annotation)}` as a "
                f"dependency into `{get_full_qualname(provider.call)}` which is "
                "not registered or set in the scoped context."
            )

    @contextlib.contextmanager
    def override(self, interface: AnyInterface, instance: Any) -> Iterator[None]:
        """
        Override the provider for the specified interface with a specific instance.
        """
        if not self.testing:
            raise RuntimeError(
                "The `override` method can only be used in testing mode."
            )
        if not self.is_registered(interface) and self.strict:
            raise LookupError(
                f"The provider interface `{get_full_qualname(interface)}` "
                "not registered."
            )
        self._override_instances[interface] = instance
        yield
        del self._override_instances[interface]

    ############################
    # Testing Methods
    ############################

    def _patch_test_resolver(self, interface: type[Any], instance: Any) -> Any:
        """Patch the test resolver for the instance."""
        if interface in self._override_instances:
            return self._override_instances[interface]

        if not hasattr(instance, "__dict__") or hasattr(
            instance, "__resolver_getter__"
        ):
            return instance

        wrapped = {
            name: value.interface
            for name, value in instance.__dict__.items()
            if isinstance(value, InstanceProxy)
        }

        def __resolver_getter__(name: str) -> Any:
            if name in wrapped:
                _interface = wrapped[name]
                # Resolve the dependency if it's wrapped
                return self.resolve(_interface)
            raise LookupError

        # Attach the resolver getter to the instance
        instance.__resolver_getter__ = __resolver_getter__

        if not hasattr(instance.__class__, "__getattribute_patched__"):

            def __getattribute__(_self: Any, name: str) -> Any:
                # Skip the resolver getter
                if name in {"__resolver_getter__"}:
                    return object.__getattribute__(_self, name)

                if hasattr(_self, "__resolver_getter__"):
                    try:
                        return _self.__resolver_getter__(name)
                    except LookupError:
                        pass

                # Fall back to default behavior
                return object.__getattribute__(_self, name)

            # Apply the patched resolver if wrapped attributes exist
            instance.__class__.__getattribute__ = __getattribute__
            instance.__class__.__getattribute_patched__ = True

        return instance

    ############################
    # Injector Methods
    ############################

    @overload
    def inject(self, func: Callable[P, T]) -> Callable[P, T]: ...

    @overload
    def inject(self) -> Callable[[Callable[P, T]], Callable[P, T]]: ...

    def inject(
        self, func: Callable[P, T] | None = None
    ) -> Callable[[Callable[P, T]], Callable[P, T]] | Callable[P, T]:
        """Decorator to inject dependencies into a callable."""

        def decorator(call: Callable[P, T]) -> Callable[P, T]:
            return self._inject(call)

        if func is None:
            return decorator
        return decorator(func)

    def run(self, func: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
        """Run the given function with injected dependencies."""
        return self._inject(func)(*args, **kwargs)

    def _inject(self, call: Callable[P, T]) -> Callable[P, T]:
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
                    self.logger.debug(
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

    ############################
    # Module Methods
    ############################

    def register_module(
        self, module: Module | type[Module] | Callable[[Container], None] | str
    ) -> None:
        """Register a module as a callable, module type, or module instance."""
        # Callable Module
        if inspect.isfunction(module):
            module(self)
            return

        # Module path
        if isinstance(module, str):
            module = import_string(module)

        # Class based Module or Module type
        if inspect.isclass(module) and issubclass(module, Module):
            module = module()

        if isinstance(module, Module):
            module.configure(self)
            for provider_name, decorator_args in module.providers:
                obj = getattr(module, provider_name)
                self.provider(
                    scope=decorator_args.scope,
                    override=decorator_args.override,
                )(obj)

    ############################
    # Scanner Methods
    ############################

    def scan(
        self,
        /,
        packages: ModuleType | str | Iterable[ModuleType | str],
        *,
        tags: Iterable[str] | None = None,
    ) -> None:
        """Scan packages or modules for decorated members and inject dependencies."""
        dependencies: list[ScannedDependency] = []

        if isinstance(packages, Iterable) and not isinstance(packages, str):
            scan_packages: Iterable[ModuleType | str] = packages
        else:
            scan_packages = cast(Iterable[Union[ModuleType, str]], [packages])

        for package in scan_packages:
            dependencies.extend(self._scan_package(package, tags=tags))

        for dependency in dependencies:
            decorator = self.inject()(dependency.member)
            setattr(dependency.module, dependency.member.__name__, decorator)

    def _scan_package(
        self,
        package: ModuleType | str,
        *,
        tags: Iterable[str] | None = None,
    ) -> list[ScannedDependency]:
        """Scan a package or module for decorated members."""
        tags = tags or []
        if isinstance(package, str):
            package = importlib.import_module(package)

        package_path = getattr(package, "__path__", None)

        if not package_path:
            return self._scan_module(package, tags=tags)

        dependencies: list[ScannedDependency] = []

        for module_info in pkgutil.walk_packages(
            path=package_path, prefix=package.__name__ + "."
        ):
            module = importlib.import_module(module_info.name)
            dependencies.extend(self._scan_module(module, tags=tags))

        return dependencies

    def _scan_module(
        self, module: ModuleType, *, tags: Iterable[str]
    ) -> list[ScannedDependency]:
        """Scan a module for decorated members."""
        dependencies: list[ScannedDependency] = []

        for _, member in inspect.getmembers(module):
            if getattr(member, "__module__", None) != module.__name__ or not callable(
                member
            ):
                continue

            decorator_args: InjectableDecoratorArgs = getattr(
                member,
                "__injectable__",
                InjectableDecoratorArgs(wrapped=False, tags=[]),
            )

            if tags and (
                decorator_args.tags
                and not set(decorator_args.tags).intersection(tags)
                or not decorator_args.tags
            ):
                continue

            if decorator_args.wrapped:
                dependencies.append(
                    self._create_scanned_dependency(member=member, module=module)
                )
                continue

            # Get by Marker
            for parameter in get_typed_parameters(member):
                if is_marker(parameter.default):
                    dependencies.append(
                        self._create_scanned_dependency(member=member, module=module)
                    )
                    continue

        return dependencies

    def _create_scanned_dependency(
        self, member: Any, module: ModuleType
    ) -> ScannedDependency:
        """Create a `Dependency` object from the scanned member and module."""
        if hasattr(member, "__wrapped__"):
            member = member.__wrapped__
        return ScannedDependency(member=member, module=module)


############################
# Decorators
############################


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


def provider(
    *, scope: Scope, override: bool = False
) -> Callable[[Callable[Concatenate[M, P], T]], Callable[Concatenate[M, P], T]]:
    """Decorator for marking a function or method as a provider in a AnyDI module."""

    def decorator(
        target: Callable[Concatenate[M, P], T],
    ) -> Callable[Concatenate[M, P], T]:
        setattr(
            target,
            "__provider__",
            ProviderDecoratorArgs(scope=scope, override=override),
        )
        return target

    return decorator


@overload
def injectable(func: Callable[P, T]) -> Callable[P, T]: ...


@overload
def injectable(
    *, tags: Iterable[str] | None = None
) -> Callable[[Callable[P, T]], Callable[P, T]]: ...


def injectable(
    func: Callable[P, T] | None = None,
    tags: Iterable[str] | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]] | Callable[P, T]:
    """Decorator for marking a function or method as requiring dependency injection."""

    def decorator(inner: Callable[P, T]) -> Callable[P, T]:
        setattr(
            inner,
            "__injectable__",
            InjectableDecoratorArgs(wrapped=True, tags=tags),
        )
        return inner

    if func is None:
        return decorator

    return decorator(func)
