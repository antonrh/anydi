"""AnyDI core implementation module."""

from __future__ import annotations

import contextlib
import functools
import inspect
import logging
import types
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator, Iterable, Iterator
from contextvars import ContextVar
from typing import Annotated, Any, Callable, TypeVar, cast, overload

from typing_extensions import ParamSpec, Self, get_args, get_origin

from ._async import run_sync
from ._context import InstanceContext
from ._decorators import is_provided
from ._module import ModuleDef, ModuleRegistrar
from ._provider import Provider, ProviderDef, ProviderKind
from ._scan import PackageOrIterable, Scanner
from ._scope import ALLOWED_SCOPES, Scope
from ._typing import (
    NOT_SET,
    Event,
    get_typed_annotation,
    get_typed_parameters,
    is_async_context_manager,
    is_context_manager,
    is_event_type,
    is_inject_marker,
    is_iterator_type,
    is_none_type,
    type_repr,
)

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
        self._resources: dict[str, list[Any]] = defaultdict(list)
        self._singleton_context = InstanceContext()
        self._request_context_var: ContextVar[InstanceContext | None] = ContextVar(
            "request_context", default=None
        )
        self._unresolved_interfaces: set[Any] = set()
        self._inject_cache: dict[Callable[..., Any], Callable[..., Any]] = {}

        # Components
        self._modules = ModuleRegistrar(self)
        self._scanner = Scanner(self)

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

    def _get_instance_context(self, scope: Scope) -> InstanceContext:
        """Get the instance context for the specified scope."""
        if scope == "singleton":
            return self._singleton_context
        return self._get_request_context()

    ############################
    # Provider Methods
    ############################

    def register(
        self,
        interface: Any,
        call: Callable[..., Any],
        *,
        scope: Scope,
        override: bool = False,
    ) -> Provider:
        """Register a provider for the specified interface."""
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
        /,
        **defaults: Any,
    ) -> Provider:
        """Register a provider with the specified scope."""
        name = type_repr(call)
        kind = ProviderKind.from_call(call)

        # Validate scope if it provided
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

        if isinstance(interface, str):
            interface = get_typed_annotation(interface, globalns, module)

        # If the callable is an iterator, return the actual type
        if is_iterator_type(interface) or is_iterator_type(get_origin(interface)):
            if args := get_args(interface):
                interface = args[0]
                # If the callable is a generator, return the resource type
                if is_none_type(interface):
                    interface = type(f"Event_{uuid.uuid4().hex}", (Event,), {})
            else:
                raise TypeError(
                    f"Cannot use `{name}` resource type annotation "
                    "without actual type argument."
                )

        # None interface is not allowed
        if is_none_type(interface):
            raise TypeError(f"Missing `{name}` provider return annotation.")

        # Check for existing provider
        if interface in self._providers and not override:
            raise LookupError(
                f"The provider interface `{type_repr(interface)}` already registered."
            )

        unresolved_parameter = None
        unresolved_exc: LookupError | None = None
        parameters: list[inspect.Parameter] = []
        scopes: dict[Scope, Provider] = {}

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
                sub_provider = self._get_or_register_provider(parameter.annotation)
            except LookupError as exc:
                if self._parameter_has_default(parameter, **defaults):
                    continue
                unresolved_parameter = parameter
                unresolved_exc = exc
                continue

            # Store first provider for each scope
            if sub_provider.scope not in scopes:
                scopes[sub_provider.scope] = sub_provider

            parameters.append(parameter)

        # Check for unresolved parameters
        if unresolved_parameter:
            if scope not in ("singleton", "transient"):
                self._unresolved_interfaces.add(interface)
            else:
                raise LookupError(
                    f"The provider `{name}` depends on `{unresolved_parameter.name}` "
                    f"of type `{type_repr(unresolved_parameter.annotation)}`, "
                    "which has not been registered or set. To resolve this, ensure "
                    f"that `{unresolved_parameter.name}` is registered before "
                    f"attempting to use it."
                ) from unresolved_exc

        # Check scope compatibility
        for sub_provider in scopes.values():
            if sub_provider.scope not in ALLOWED_SCOPES.get(scope, []):
                raise ValueError(
                    f"The provider `{name}` with a `{scope}` scope cannot "
                    f"depend on `{sub_provider}` with a `{sub_provider.scope}` scope. "
                    "Please ensure all providers are registered with matching scopes."
                )

        provider = Provider(
            call=call,
            scope=scope,
            interface=interface,
            name=name,
            kind=kind,
            parameters=parameters,
        )

        self._set_provider(provider)
        return provider

    @staticmethod
    def _validate_provider_scope(scope: Scope, name: str, kind: ProviderKind) -> None:
        """Validate the provider scope."""
        if scope not in (allowed_scopes := get_args(Scope)):
            raise ValueError(
                f"The provider `{name}` scope is invalid. Only the following "
                f"scopes are supported: {', '.join(allowed_scopes)}. "
                "Please use one of the supported scopes when registering a provider."
            )
        if scope == "transient" and ProviderKind.is_resource(kind):
            raise TypeError(
                f"The resource provider `{name}` is attempting to register "
                "with a transient scope, which is not allowed."
            )

    def _get_provider(self, interface: Any) -> Provider:
        """Get provider by interface."""
        try:
            return self._providers[interface]
        except KeyError as exc:
            raise LookupError(
                f"The provider interface for `{type_repr(interface)}` has "
                "not been registered. Please ensure that the provider interface is "
                "properly registered before attempting to use it."
            ) from exc

    def _get_or_register_provider(self, interface: Any, /, **defaults: Any) -> Provider:
        """Get or register a provider by interface."""
        try:
            return self._providers[interface]
        except KeyError:
            if inspect.isclass(interface) and is_provided(interface):
                return self._register_provider(
                    interface,
                    interface.__provided__["scope"],
                    NOT_SET,
                    **defaults,
                )
            raise LookupError(
                f"The provider interface `{type_repr(interface)}` is either not "
                "registered, not provided, or not set in the scoped context. "
                "Please ensure that the provider interface is properly registered and "
                "that the class is decorated with a scope before attempting to use it."
            ) from None

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

    @staticmethod
    def _parameter_has_default(
        parameter: inspect.Parameter, /, **defaults: Any
    ) -> bool:
        has_default_in_kwargs = parameter.name in defaults if defaults else False
        has_default = parameter.default is not inspect.Parameter.empty
        return has_default_in_kwargs or has_default

    ############################
    # Instance Methods
    ############################

    @overload
    def resolve(self, interface: type[T]) -> T: ...

    @overload
    def resolve(self, interface: T) -> T: ...  # type: ignore

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

    def _resolve_or_create(
        self, interface: Any, create: bool, /, **defaults: Any
    ) -> Any:
        """Internal method to handle instance resolution and creation."""
        provider = self._get_or_register_provider(interface, **defaults)
        if provider.scope == "transient":
            return self._create_instance(provider, None, **defaults)
        context = self._get_instance_context(provider.scope)
        with context.lock():
            return (
                self._get_or_create_instance(provider, context)
                if not create
                else self._create_instance(provider, context, **defaults)
            )

    async def _aresolve_or_create(
        self, interface: Any, create: bool, /, **defaults: Any
    ) -> Any:
        """Internal method to handle instance resolution and creation asynchronously."""
        provider = self._get_or_register_provider(interface, **defaults)
        if provider.scope == "transient":
            return await self._acreate_instance(provider, None, **defaults)
        context = self._get_instance_context(provider.scope)
        async with context.alock():
            return (
                await self._aget_or_create_instance(provider, context)
                if not create
                else await self._acreate_instance(provider, context, **defaults)
            )

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

            return await run_sync(_create)

        instance = await run_sync(provider.call, **provider_kwargs)
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
            provided_kwargs[parameter.name] = self._get_provider_instance(
                provider, parameter, context, **defaults
            )
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
        return instance

    async def _aget_provided_kwargs(
        self, provider: Provider, context: InstanceContext | None, /, **defaults: Any
    ) -> dict[str, Any]:
        """Asynchronously retrieve the arguments for a provider."""
        provided_kwargs = {}
        for parameter in provider.parameters:
            provided_kwargs[parameter.name] = await self._aget_provider_instance(
                provider, parameter, context, **defaults
            )
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
        return instance

    def _resolve_parameter(
        self, provider: Provider, parameter: inspect.Parameter
    ) -> Any:
        self._validate_resolvable_parameter(provider, parameter)
        return self._resolve_or_create(parameter.annotation, False)

    async def _aresolve_parameter(
        self, provider: Provider, parameter: inspect.Parameter
    ) -> Any:
        self._validate_resolvable_parameter(provider, parameter)
        return await self._aresolve_or_create(parameter.annotation, False)

    def _validate_resolvable_parameter(
        self, provider: Provider, parameter: inspect.Parameter
    ) -> None:
        """Ensure that the specified interface is resolved."""
        if parameter.annotation in self._unresolved_interfaces:
            raise LookupError(
                f"You are attempting to get the parameter `{parameter.name}` with the "
                f"annotation `{type_repr(parameter.annotation)}` as a "
                f"dependency into `{type_repr(provider.call)}` which is "
                "not registered or set in the scoped context."
            )

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
        if not injected_params:
            self._inject_cache[call] = call
            return call

        if inspect.iscoroutinefunction(call):

            @functools.wraps(call)
            async def awrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                for name, annotation in injected_params.items():
                    kwargs[name] = await self.aresolve(annotation)
                return cast(T, await call(*args, **kwargs))

            self._inject_cache[call] = awrapper

            return awrapper  # type: ignore

        @functools.wraps(call)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            for name, annotation in injected_params.items():
                kwargs[name] = self.resolve(annotation)
            return call(*args, **kwargs)

        self._inject_cache[call] = wrapper

        return wrapper

    def _get_injected_params(self, call: Callable[..., Any]) -> dict[str, Any]:
        """Get the injected parameters of a callable object."""
        injected_params: dict[str, Any] = {}
        for parameter in get_typed_parameters(call):
            interface, should_inject = self.validate_injected_parameter(
                parameter, call=call
            )
            if should_inject:
                injected_params[parameter.name] = interface
        return injected_params

    @staticmethod
    def _unwrap_injected_parameter(parameter: inspect.Parameter) -> inspect.Parameter:
        if get_origin(parameter.annotation) is not Annotated:
            return parameter

        origin, *metadata = get_args(parameter.annotation)

        if not metadata or not is_inject_marker(metadata[-1]):
            return parameter

        if is_inject_marker(parameter.default):
            raise TypeError(
                "Cannot specify `Inject` in `Annotated` and "
                f"default value together for '{parameter.name}'"
            )

        if parameter.default is not inspect.Parameter.empty:
            return parameter

        marker = metadata[-1]
        new_metadata = metadata[:-1]
        if new_metadata:
            new_annotation = Annotated.__class_getitem__((origin, *new_metadata))  # type: ignore
        else:
            new_annotation = origin
        return parameter.replace(annotation=new_annotation, default=marker)

    def validate_injected_parameter(
        self, parameter: inspect.Parameter, *, call: Callable[..., Any]
    ) -> tuple[Any, bool]:
        """Validate an injected parameter."""
        parameter = self._unwrap_injected_parameter(parameter)
        interface = parameter.annotation

        if not is_inject_marker(parameter.default):
            return interface, False

        if interface is inspect.Parameter.empty:
            raise TypeError(
                f"Missing `{type_repr(call)}` parameter `{parameter.name}` annotation."
            )

        # Set inject marker interface
        parameter.default.interface = interface

        # TODO: temporary disable until strict is enforced (remove False)
        if False and not self.has_provider_for(interface):
            raise LookupError(
                f"`{type_repr(call)}` has an unknown dependency parameter "
                f"`{parameter.name}` with an annotation of "
                f"`{type_repr(interface)}`."
            )

        return interface, True

    ############################
    # Module Methods
    ############################

    def register_module(self, module: ModuleDef) -> None:
        """Register a module as a callable, module type, or module instance."""
        self._modules.register(module)

    ############################
    # Scanner Methods
    ############################

    def scan(
        self, /, packages: PackageOrIterable, *, tags: Iterable[str] | None = None
    ) -> None:
        self._scanner.scan(packages=packages, tags=tags)

    ############################
    # Testing
    ############################

    @contextlib.contextmanager
    def override(self, interface: Any, instance: Any) -> Iterator[None]:
        raise RuntimeError(
            "Dependency overriding is not supported in this container.\n"
            "Wrap your container with `anydi.testing.Container` instead.\n"
            "Example:\n\n"
            "    container = TestContainer.from_container(container)"
        )
