"""AnyDI core implementation module."""

from __future__ import annotations

import contextlib
import inspect
import types
import uuid
from contextvars import ContextVar
from functools import wraps
from typing import (
    Any,
    AsyncContextManager,
    AsyncIterator,
    Awaitable,
    Callable,
    ContextManager,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
    TypeVar,
    cast,
    overload,
)

from typing_extensions import ParamSpec, final, get_args, get_origin

try:
    from types import NoneType
except ImportError:
    NoneType = type(None)  # type: ignore[misc]


from ._context import (
    RequestContext,
    ResourceScopedContext,
    ScopedContext,
    SingletonContext,
    TransientContext,
)
from ._logger import logger
from ._module import Module, ModuleRegistry
from ._scanner import Scanner
from ._types import AnyInterface, Interface, Provider, Scope, is_marker
from ._utils import (
    get_full_qualname,
    get_typed_parameters,
    get_typed_return_annotation,
    has_resource_origin,
    is_builtin_type,
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
    """AnyDI is a dependency injection container.

    Args:
        modules: Optional sequence of modules to register during initialization.
    """

    def __init__(
        self,
        *,
        providers: Mapping[type[Any], Provider] | None = None,
        modules: Sequence[Module | type[Module] | Callable[[Container], None]]
        | None = None,
        strict: bool = False,
    ) -> None:
        """Initialize the AnyDI instance.

        Args:
            providers: Optional mapping of providers to register during initialization.
            modules: Optional sequence of modules to register during initialization.
            strict: Whether to enable strict mode. Defaults to False.
        """
        self._providers: dict[type[Any], Provider] = {}
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
        providers = providers or {}
        for interface, provider in providers.items():
            self.register(interface, provider.obj, scope=provider.scope)

        # Register modules
        modules = modules or []
        for module in modules:
            self.register_module(module)

    @property
    def strict(self) -> bool:
        """Check if strict mode is enabled.

        Returns:
            True if strict mode is enabled, False otherwise.
        """
        return self._strict

    @property
    def providers(self) -> dict[type[Any], Provider]:
        """Get the registered providers.

        Returns:
            A dictionary containing the registered providers.
        """
        return self._providers

    def is_registered(self, interface: AnyInterface) -> bool:
        """Check if a provider is registered for the specified interface.

        Args:
            interface: The interface to check for a registered provider.

        Returns:
            True if a provider is registered for the interface, False otherwise.
        """
        return interface in self._providers

    def register(
        self,
        interface: AnyInterface,
        obj: Callable[..., Any],
        *,
        scope: Scope,
        override: bool = False,
    ) -> Provider:
        """Register a provider for the specified interface.

        Args:
            interface: The interface for which the provider is being registered.
            obj: The provider function or callable object.
            scope: The scope of the provider.
            override: If True, override an existing provider for the interface
                if one is already registered. Defaults to False.

        Returns:
            The registered provider.

        Raises:
            LookupError: If a provider for the interface is already registered
              and override is False.

        Notes:
            - If the provider is a resource or an asynchronous resource, and the
              interface is None, an Event type will be automatically created and used
              as the interface.
            - The provider will be validated for its scope, type, and matching scopes.
        """
        provider = Provider(obj=obj, scope=scope)

        # Create Event type
        if provider.is_resource and (interface is NoneType or interface is None):
            interface = type(f"Event{uuid.uuid4().hex}", (), {})

        if interface in self._providers:
            if override:
                self._providers[interface] = provider
                return provider

            raise LookupError(
                f"The provider interface `{get_full_qualname(interface)}` "
                "already registered."
            )

        # Validate provider
        self._validate_provider_scope(provider)
        self._validate_provider_type(provider)
        self._validate_provider_match_scopes(interface, provider)

        self._providers[interface] = provider
        return provider

    def unregister(self, interface: AnyInterface) -> None:
        """Unregister a provider by interface.

        Args:
            interface: The interface of the provider to unregister.

        Raises:
            LookupError: If the provider interface is not registered.

        Notes:
            - The method cleans up any scoped context instance associated with
              the provider's scope.
            - The method removes the provider reference from the internal dictionary
              of registered providers.
        """
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
        self._providers.pop(interface, None)

    def _get_provider(self, interface: AnyInterface) -> Provider:
        """Get provider by interface.

        Args:
            interface: The interface for which to retrieve the provider.

        Returns:
            Provider: The provider object associated with the interface.

        Raises:
            LookupError: If the provider interface has not been registered.
        """
        try:
            return self._providers[interface]
        except KeyError as exc:
            raise LookupError(
                f"The provider interface for `{get_full_qualname(interface)}` has "
                "not been registered. Please ensure that the provider interface is "
                "properly registered before attempting to use it."
            ) from exc

    def _get_or_register_provider(self, interface: AnyInterface) -> Provider:
        """Get or register a provider by interface.

        Args:
            interface: The interface for which to retrieve the provider.

        Returns:
            Provider: The provider object associated with the interface.

        Raises:
            LookupError: If the provider interface has not been registered.
        """
        try:
            return self._get_provider(interface)
        except LookupError:
            if (
                not self.strict
                and inspect.isclass(interface)
                and not is_builtin_type(interface)
                and interface is not inspect._empty  # noqa
            ):
                # Try to get defined scope
                scope = getattr(interface, "__scope__", None)
                # Try to detect scope
                if scope is None:
                    scope = self._detect_scope(interface)
                return self.register(interface, interface, scope=scope or "transient")
            raise

    def _validate_provider_scope(self, provider: Provider) -> None:
        """Validate the scope of a provider.

        Args:
            provider: The provider to validate.

        Raises:
            ValueError: If the scope provided is invalid.
        """
        if provider.scope not in get_args(Scope):
            raise ValueError(
                "The scope provided is invalid. Only the following scopes are "
                f"supported: {', '.join(get_args(Scope))}. Please use one of the "
                "supported scopes when registering a provider."
            )

    def _validate_provider_type(self, provider: Provider) -> None:
        """Validate the type of provider.

        Args:
            provider: The provider to validate.

        Raises:
            TypeError: If the provider has an invalid type.
        """
        if provider.is_function or provider.is_class:
            return

        if provider.is_resource:
            if provider.scope == "transient":
                raise TypeError(
                    f"The resource provider `{provider}` is attempting to register "
                    "with a transient scope, which is not allowed. Please update the "
                    "provider's scope to an appropriate value before registering it."
                )
            return

        raise TypeError(
            f"The provider `{provider.obj}` is invalid because it is not a callable "
            "object. Only callable providers are allowed. Please update the provider "
            "to a callable object before attempting to register it."
        )

    def _validate_provider_match_scopes(
        self, interface: AnyInterface, provider: Provider
    ) -> None:
        """Validate that the provider and its dependencies have matching scopes.

        Args:
            interface: The interface associated with the provider.
            provider: The provider to validate.

        Raises:
            ValueError: If the provider and its dependencies have mismatched scopes.
            TypeError: If a dependency is missing an annotation.
        """
        related_providers = []

        for parameter in provider.parameters:
            if parameter.annotation is inspect._empty:  # noqa
                raise TypeError(
                    f"Missing provider `{provider}` "
                    f"dependency `{parameter.name}` annotation."
                )
            try:
                sub_provider = self._get_or_register_provider(parameter.annotation)
            except LookupError:
                raise ValueError(
                    f"The provider `{get_full_qualname(provider.obj)}` depends on "
                    f"`{parameter.name}` of type "
                    f"`{get_full_qualname(parameter.annotation)}`, which "
                    "has not been registered. To resolve this, ensure that "
                    f"`{parameter.name}` is registered before attempting to use it."
                ) from None
            related_providers.append(sub_provider)

        for related_provider in related_providers:
            left_scope, right_scope = related_provider.scope, provider.scope
            allowed_scopes = ALLOWED_SCOPES.get(right_scope) or []
            if left_scope not in allowed_scopes:
                raise ValueError(
                    f"The provider `{provider}` with a {provider.scope} scope was "
                    "attempted to be registered with the provider "
                    f"`{related_provider}` with a `{related_provider.scope}` scope, "
                    "which is not allowed. Please ensure that all providers are "
                    "registered with matching scopes."
                )

    def _detect_scope(self, obj: Callable[..., Any]) -> Scope | None:
        """Detect the scope for a provider.

        Args:
            obj: The provider to detect the auto scope for.
        Returns:
            The auto scope, or None if the auto scope cannot be detected.
        """
        has_transient, has_request, has_singleton = False, False, False
        for parameter in get_typed_parameters(obj):
            sub_provider = self._get_or_register_provider(parameter.annotation)
            if not has_transient and sub_provider.scope == "transient":
                has_transient = True
            if not has_request and sub_provider.scope == "request":
                has_request = True
            if not has_singleton and sub_provider.scope == "singleton":
                has_singleton = True
        if has_transient:
            return "transient"
        if has_request:
            return "request"
        if has_singleton:
            return "singleton"
        return None

    def register_module(
        self, module: Module | type[Module] | Callable[[Container], None]
    ) -> None:
        """Register a module as a callable, module type, or module instance.

        Args:
            module: The module to register.
        """
        self._modules.register(module)

    def start(self) -> None:
        """Start the singleton context."""
        for interface, provider in self._providers.items():
            if provider.scope == "singleton":
                self.resolve(interface)  # noqa

    def close(self) -> None:
        """Close the singleton context."""
        self._singleton_context.close()

    def request_context(self) -> ContextManager[None]:
        """Obtain a context manager for the request-scoped context.

        Returns:
            A context manager for the request-scoped context.
        """
        return contextlib.contextmanager(self._request_context)()

    def _request_context(self) -> Iterator[None]:
        """Internal method that manages the request-scoped context.

        Yields:
            Yield control to the code block within the request context.
        """
        context = RequestContext(self)
        token = self._request_context_var.set(context)
        with context:
            yield
            self._request_context_var.reset(token)

    async def astart(self) -> None:
        """Start the singleton context asynchronously."""
        for interface, provider in self._providers.items():
            if provider.scope == "singleton":
                await self.aresolve(interface)  # noqa

    async def aclose(self) -> None:
        """Close the singleton context asynchronously."""
        await self._singleton_context.aclose()

    def arequest_context(self) -> AsyncContextManager[None]:
        """Obtain an async context manager for the request-scoped context.

        Returns:
            An async context manager for the request-scoped context.
        """
        return contextlib.asynccontextmanager(self._arequest_context)()

    async def _arequest_context(self) -> AsyncIterator[None]:
        """Internal method that manages the async request-scoped context.

        Yields:
            Yield control to the code block within the request context.
        """
        context = RequestContext(self)
        token = self._request_context_var.set(context)
        async with context:
            yield
            self._request_context_var.reset(token)

    def _get_request_context(self) -> RequestContext:
        """Get the current request context.

        Returns:
            RequestContext: The current request context.

        Raises:
            LookupError: If the request context has not been started.
        """
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
            scoped_context = self._get_scoped_context(provider.scope)
            if isinstance(scoped_context, ResourceScopedContext):
                scoped_context.delete(interface)

    @overload
    def resolve(self, interface: Interface[T]) -> T: ...

    @overload
    def resolve(self, interface: T) -> T: ...

    def resolve(self, interface: Interface[T]) -> T:
        """Resolve an instance by interface.

        Args:
            interface: The interface type.

        Returns:
            The instance of the interface.

        Raises:
            LookupError: If the provider for the interface is not registered.
        """
        if interface in self._override_instances:
            return cast(T, self._override_instances[interface])

        provider = self._get_or_register_provider(interface)
        scoped_context = self._get_scoped_context(provider.scope)
        return scoped_context.get(interface, provider)

    @overload
    async def aresolve(self, interface: Interface[T]) -> T: ...

    @overload
    async def aresolve(self, interface: T) -> T: ...

    async def aresolve(self, interface: Interface[T]) -> T:
        """Resolve an instance by interface asynchronously.

        Args:
            interface: The interface type.

        Returns:
            The instance of the interface.

        Raises:
            LookupError: If the provider for the interface is not registered.
        """
        if interface in self._override_instances:
            return cast(T, self._override_instances[interface])

        provider = self._get_or_register_provider(interface)
        scoped_context = self._get_scoped_context(provider.scope)
        return await scoped_context.aget(interface, provider)

    def is_resolved(self, interface: AnyInterface) -> bool:
        """Check if an instance by interface exists.

        Args:
            interface: The interface type.

        Returns:
            True if the instance exists, otherwise False.
        """
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
        """Release an instance by interface.

        Args:
            interface: The interface type.

        Raises:
            LookupError: If the provider for the interface is not registered.
        """
        provider = self._get_provider(interface)
        scoped_context = self._get_scoped_context(provider.scope)
        if isinstance(scoped_context, ResourceScopedContext):
            scoped_context.delete(interface)

    def _get_scoped_context(self, scope: Scope) -> ScopedContext:
        """Get the scoped context based on the specified scope.

        Args:
            scope: The scope of the provider.

        Returns:
            The scoped context, or None if the scope is not applicable.
        """
        if scope == "singleton":
            return self._singleton_context
        elif scope == "request":
            request_context = self._get_request_context()
            return request_context
        return self._transient_context

    @contextlib.contextmanager
    def override(self, interface: AnyInterface, instance: Any) -> Iterator[None]:
        """Override the provider for the specified interface with a specific instance.

        Args:
            interface: The interface type to override.
            instance: The instance to use as the override.

        Yields:
            None

        Raises:
            LookupError: If the provider for the interface is not registered.
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
        """Decorator to register a provider function with the specified scope.

        Args:
            scope : The scope of the provider.
            override: Whether the provider should override an existing provider
                for the same interface. Defaults to False.

        Returns:
            The decorator function.
        """

        def decorator(func: Callable[P, T]) -> Callable[P, T]:
            interface = self._get_provider_annotation(func)
            self.register(interface, func, scope=scope, override=override)
            return func

        return decorator

    @overload
    def inject(self, obj: Callable[P, T]) -> Callable[P, T]: ...

    @overload
    def inject(self) -> Callable[[Callable[P, T]], Callable[P, T]]: ...

    def inject(
        self, obj: Callable[P, T | Awaitable[T]] | None = None
    ) -> (
        Callable[[Callable[P, T | Awaitable[T]]], Callable[P, T | Awaitable[T]]]
        | Callable[P, T | Awaitable[T]]
    ):
        """Decorator to inject dependencies into a callable.

        Args:
            obj: The callable object to be decorated. If None, returns
                the decorator itself.

        Returns:
            The decorated callable object or decorator function.
        """

        def decorator(
            obj: Callable[P, T | Awaitable[T]],
        ) -> Callable[P, T | Awaitable[T]]:
            injected_params = self._get_injected_params(obj)

            if inspect.iscoroutinefunction(obj):

                @wraps(obj)
                async def awrapped(*args: P.args, **kwargs: P.kwargs) -> T:
                    for name, annotation in injected_params.items():
                        kwargs[name] = await self.aresolve(annotation)
                    return cast(T, await obj(*args, **kwargs))

                return awrapped

            @wraps(obj)
            def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
                for name, annotation in injected_params.items():
                    kwargs[name] = self.resolve(annotation)
                return cast(T, obj(*args, **kwargs))

            return wrapped

        if obj is None:
            return decorator
        return decorator(obj)

    def run(self, obj: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
        """Run the given function with injected dependencies.

        Args:
            obj: The callable object.
            args: The positional arguments to pass to the object.
            kwargs: The keyword arguments to pass to the object.

        Returns:
            The result of the callable object.
        """
        return self.inject(obj)(*args, **kwargs)

    def scan(
        self,
        /,
        packages: types.ModuleType | str | Iterable[types.ModuleType | str],
        *,
        tags: Iterable[str] | None = None,
    ) -> None:
        """Scan packages or modules for decorated members and inject dependencies.

        Args:
            packages: A single package or module to scan,
                or an iterable of packages or modules to scan.
            tags: Optional list of tags to filter the scanned members. Only members
                with at least one matching tag will be scanned. Defaults to None.
        """
        self._scanner.scan(packages, tags=tags)

    def _get_provider_annotation(self, obj: Callable[..., Any]) -> Any:
        """Retrieve the provider return annotation from a callable object.

        Args:
            obj: The callable object (provider).

        Returns:
            The provider return annotation.

        Raises:
            TypeError: If the provider return annotation is missing or invalid.
        """
        annotation = get_typed_return_annotation(obj)

        if annotation is None:
            raise TypeError(
                f"Missing `{get_full_qualname(obj)}` provider return annotation."
            )

        origin = get_origin(annotation)

        if has_resource_origin(origin):
            args = get_args(annotation)
            if args:
                return args[0]
            else:
                raise TypeError(
                    f"Cannot use `{get_full_qualname(obj)}` resource type annotation "
                    "without actual type."
                )

        return annotation

    def _get_injected_params(self, obj: Callable[..., Any]) -> dict[str, Any]:
        """Get the injected parameters of a callable object.

        Args:
            obj: The callable object.

        Returns:
            A dictionary containing the names and annotations
                of the injected parameters.
        """
        injected_params = {}
        for parameter in get_typed_parameters(obj):
            if not is_marker(parameter.default):
                continue
            try:
                self._validate_injected_parameter(obj, parameter)
            except LookupError as exc:
                if not self.strict:
                    logger.debug(
                        f"Cannot validate the `{get_full_qualname(obj)}` parameter "
                        f"`{parameter.name}` with an annotation of "
                        f"`{get_full_qualname(parameter.annotation)} due to being "
                        "in non-strict mode. It will be validated at the first call."
                    )
                else:
                    raise exc
            injected_params[parameter.name] = parameter.annotation
        return injected_params

    def _validate_injected_parameter(
        self, obj: Callable[..., Any], parameter: inspect.Parameter
    ) -> None:
        """Validate an injected parameter.

        Args:
            obj: The callable object.
            parameter: The parameter to validate.

        Raises:
            TypeError: If the parameter annotation is missing or an unknown dependency.
        """
        if parameter.annotation is inspect._empty:  # noqa
            raise TypeError(
                f"Missing `{get_full_qualname(obj)}` parameter "
                f"`{parameter.name}` annotation."
            )

        if not self.is_registered(parameter.annotation):
            raise LookupError(
                f"`{get_full_qualname(obj)}` has an unknown dependency parameter "
                f"`{parameter.name}` with an annotation of "
                f"`{get_full_qualname(parameter.annotation)}`."
            )


def transient(target: T) -> T:
    """Decorator for marking a class as transient scope.

    Args:
        target: The target class to be decorated.

    Returns:
        The decorated target class.
    """
    setattr(target, "__scope__", "transient")
    return target


def request(target: T) -> T:
    """Decorator for marking a class as request scope.

    Args:
        target: The target class to be decorated.

    Returns:
        The decorated target class.
    """
    setattr(target, "__scope__", "request")
    return target


def singleton(target: T) -> T:
    """Decorator for marking a class as singleton scope.

    Args:
        target: The target class to be decorated.

    Returns:
        The decorated target class.
    """
    setattr(target, "__scope__", "singleton")
    return target
