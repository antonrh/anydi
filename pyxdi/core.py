from __future__ import annotations

import contextlib
import importlib
import inspect
import pkgutil
import types
import typing as t
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from functools import cached_property, wraps

from typing_extensions import Annotated, ParamSpec, Self, get_args, get_origin

try:
    from types import NoneType
except ImportError:
    NoneType = type(None)  # type: ignore[assignment,misc]


from .exceptions import (
    AnnotationError,
    InvalidScopeError,
    ProviderError,
    ScopeMismatchError,
    UnknownDependencyError,
)
from .utils import get_full_qualname, get_signature, run_async

Scope = t.Literal["transient", "singleton", "request"]
T = t.TypeVar("T", bound=t.Any)
P = ParamSpec("P")

ALLOWED_SCOPES: t.Dict[Scope, t.List[Scope]] = {
    "singleton": ["singleton"],
    "request": ["request", "singleton"],
    "transient": ["transient", "singleton", "request"],
}


@dataclass(frozen=True)
class Provider:
    obj: t.Callable[..., t.Any]
    scope: Scope

    def __str__(self) -> str:
        return self.name

    @cached_property
    def name(self) -> str:
        return get_full_qualname(self.obj)

    @cached_property
    def parameters(self) -> types.MappingProxyType[str, inspect.Parameter]:
        return get_signature(self.obj).parameters

    @cached_property
    def is_class(self) -> bool:
        return inspect.isclass(self.obj)

    @cached_property
    def is_function(self) -> bool:
        return (inspect.isfunction(self.obj) or inspect.ismethod(self.obj)) and not (
            self.is_resource or self.is_async_resource
        )

    @cached_property
    def is_coroutine(self) -> bool:
        return inspect.iscoroutinefunction(self.obj)

    @cached_property
    def is_resource(self) -> bool:
        return inspect.isgeneratorfunction(self.obj)

    @cached_property
    def is_async_resource(self) -> bool:
        return inspect.isasyncgenfunction(self.obj)


@dataclass(frozen=True)
class ScannedDependency:
    member: t.Any
    module: types.ModuleType


class DependencyMark:
    __slots__ = ()


# Dependency mark with Any type
dep = t.cast(t.Any, DependencyMark())


def named(tp: t.Type[T], name: str) -> Annotated[t.Type[T], str]:
    """
    Cast annotated type helper.
    """
    return t.cast(Annotated[t.Type[T], str], Annotated[tp, name])


@t.final
class PyxDI:
    def __init__(
        self,
        *,
        modules: t.Optional[
            t.Sequence[t.Union[Module, t.Type[Module], t.Callable[[PyxDI], None]]],
        ] = None,
    ) -> None:
        self._providers: t.Dict[t.Type[t.Any], Provider] = {}
        self._singleton_context = SingletonContext(self)
        self._request_context_var: ContextVar[t.Optional[RequestContext]] = ContextVar(
            "request_context", default=None
        )
        self._override_instances: t.Dict[t.Type[t.Any], t.Any] = {}

        # Register modules
        modules = modules or []
        for module in modules:
            self.register_module(module)

    @property
    def providers(self) -> t.Dict[t.Type[t.Any], Provider]:
        return self._providers

    # Provider

    def has_provider(self, interface: t.Type[t.Any]) -> bool:
        return interface in self._providers

    def register_provider(
        self,
        interface: t.Type[t.Any],
        obj: t.Callable[..., t.Any],
        *,
        scope: Scope,
        override: bool = False,
    ) -> Provider:
        provider = Provider(obj=obj, scope=scope)

        # Create Event type
        if (provider.is_resource or provider.is_async_resource) and (
            interface is NoneType or interface is None
        ):
            interface = type(f"Event{uuid.uuid4().hex}", (), {})

        if interface in self._providers:
            if override:
                self._providers[interface] = provider
                return provider

            raise ProviderError(
                f"The provider interface `{get_full_qualname(interface)}` "
                "already registered."
            )

        # Validate provider
        self._validate_provider_scope(provider)
        self._validate_provider_type(provider)
        self._validate_provider_match_scopes(interface, provider)

        self._providers[interface] = provider
        return provider

    def unregister_provider(self, interface: t.Type[t.Any]) -> None:
        """
        Unregister provider by interface.
        """
        if not self.has_provider(interface):
            raise ProviderError(
                "The provider interface "
                f"`{get_full_qualname(interface)}` not registered."
            )

        provider = self.get_provider(interface)

        # Cleanup scoped context instance
        try:
            scoped_context = self._get_scoped_context(provider.scope)
        except LookupError:
            pass
        else:
            if scoped_context:
                scoped_context.delete(interface)

        # Cleanup provider references
        self._providers.pop(interface, None)

    def get_provider(self, interface: t.Type[t.Any]) -> Provider:
        """
        Get provider by interface.
        """
        try:
            return self._providers[interface]
        except KeyError as exc:
            raise ProviderError(
                f"The provider interface for `{get_full_qualname(interface)}` has "
                "not been registered. Please ensure that the provider interface is "
                "properly registered before attempting to use it."
            ) from exc

    # Validators

    def _validate_provider_scope(self, provider: Provider) -> None:
        if provider.scope not in t.get_args(Scope):
            raise InvalidScopeError(
                "The scope provided is invalid. Only the following scopes are "
                f"supported: {', '.join(t.get_args(Scope))}. Please use one of the "
                "supported scopes when registering a provider."
            )

    def _validate_provider_type(self, provider: Provider) -> None:
        if provider.is_function or provider.is_class:
            return

        if provider.is_resource or provider.is_async_resource:
            if provider.scope == "transient":
                raise ProviderError(
                    f"The resource provider `{provider}` is attempting to register "
                    "with a transient scope, which is not allowed. Please update the "
                    "provider's scope to an appropriate value before registering it."
                )
            return

        raise ProviderError(
            f"The provider `{provider.obj}` is invalid because it is not a callable "
            "object. Only callable providers are allowed. Please update the provider "
            "to a callable object before attempting to register it."
        )

    def _validate_provider_match_scopes(
        self, interface: t.Type[t.Any], provider: Provider
    ) -> None:
        related_providers = []

        for parameter in provider.parameters.values():
            if parameter.annotation is inspect._empty:  # noqa
                raise AnnotationError(
                    f"Missing provider `{provider}` "
                    f"dependency `{parameter.name}` annotation."
                )
            sub_provider = self.get_provider(parameter.annotation)
            related_providers.append(sub_provider)

        for related_provider in related_providers:
            left_scope, right_scope = related_provider.scope, provider.scope
            allowed_scopes = ALLOWED_SCOPES.get(right_scope) or []
            if left_scope not in allowed_scopes:
                raise ScopeMismatchError(
                    f"The provider `{provider}` with a {provider.scope} scope was "
                    f"attempted to be registered with the provider "
                    f"`{related_provider}` with a `{related_provider.scope}` scope, "
                    f"which is not allowed. Please ensure that all providers are "
                    f"registered with matching scopes."
                )

    # Modules

    def register_module(
        self, module: t.Union[Module, t.Type[Module], t.Callable[[PyxDI], None]]
    ) -> None:
        """
        Register module as callable, module type or module instance.
        """
        # Callable Module
        if inspect.isfunction(module):
            module(self)
            return

        # Class based Module or Module type
        if inspect.isclass(module) and issubclass(module, Module):
            module = module()
        if isinstance(module, Module):
            module.configure(self)
            for provider_name, params in module.providers:
                obj = getattr(module, provider_name)
                scope, override = params["scope"], params["override"]
                self.provider(scope=scope, override=override)(obj)

    # Lifespan

    def start(self) -> None:
        self._singleton_context.start()

    def close(self) -> None:
        self._singleton_context.close()

    def request_context(self) -> t.ContextManager[None]:
        return contextlib.contextmanager(self._request_context)()

    def _request_context(self) -> t.Iterator[None]:
        context = RequestContext(self)
        token = self._request_context_var.set(context)
        with context:
            yield
            self._request_context_var.reset(token)

    # Asynchronous lifespan

    async def astart(self) -> None:
        await self._singleton_context.astart()

    async def aclose(self) -> None:
        await self._singleton_context.aclose()

    def arequest_context(self) -> t.AsyncContextManager[None]:
        return contextlib.asynccontextmanager(self._arequest_context)()

    async def _arequest_context(self) -> t.AsyncIterator[None]:
        context = RequestContext(self)
        token = self._request_context_var.set(context)
        async with context:
            yield
            self._request_context_var.reset(token)

    def _get_request_context(self) -> RequestContext:
        request_context = self._request_context_var.get()
        if request_context is None:
            raise LookupError(
                "The request context has not been started. Please ensure that "
                "the request context is properly initialized before attempting "
                "to use it."
            )
        return request_context

    # Instance

    def get_instance(self, interface: t.Type[T]) -> T:
        """
        Get instance by interface.
        """
        if interface in self._override_instances:
            return t.cast(T, self._override_instances[interface])

        provider = self.get_provider(interface)

        scoped_context = self._get_scoped_context(provider.scope)
        if scoped_context:
            return scoped_context.get(interface)
        return t.cast(T, self.create_instance(provider))

    async def aget_instance(self, interface: t.Type[T]) -> T:
        """
        Get instance by interface asynchronously.
        """
        if interface in self._override_instances:
            return t.cast(T, self._override_instances[interface])

        provider = self.get_provider(interface)

        scoped_context = self._get_scoped_context(provider.scope)
        if scoped_context:
            return await scoped_context.aget(interface)
        return t.cast(T, await self.acreate_instance(provider))

    def has_instance(self, interface: t.Type[T]) -> bool:
        """
        Check that container contains instance by interface.
        """
        try:
            provider = self.get_provider(interface)
        except ProviderError:
            return False
        scoped_context = self._get_scoped_context(provider.scope)
        if scoped_context:
            return scoped_context.has(interface)
        return True

    def _get_scoped_context(self, scope: Scope) -> t.Optional[ScopedContext]:
        if scope == "singleton":
            return self._singleton_context
        elif scope == "request":
            request_context = self._get_request_context()
            return request_context
        return None

    def create_resource(
        self, provider: Provider, *, stack: contextlib.ExitStack
    ) -> t.Any:
        args, kwargs = self._get_provider_arguments(provider)
        cm = contextlib.contextmanager(provider.obj)(*args, **kwargs)
        return stack.enter_context(cm)

    async def acreate_resource(
        self,
        provider: Provider,
        *,
        stack: contextlib.AsyncExitStack,
    ) -> t.Any:
        args, kwargs = await self._aget_provider_arguments(provider)
        cm = contextlib.asynccontextmanager(provider.obj)(*args, **kwargs)
        return await stack.enter_async_context(cm)

    def create_instance(self, provider: Provider) -> t.Any:
        self._validate_instance_is_not_resource(provider)
        if provider.is_coroutine:
            raise ProviderError(
                f"The instance for the coroutine provider `{provider}` cannot be "
                "created in synchronous mode."
            )
        args, kwargs = self._get_provider_arguments(provider)
        return provider.obj(*args, **kwargs)

    async def acreate_instance(self, provider: Provider) -> t.Any:
        self._validate_instance_is_not_resource(provider)
        args, kwargs = await self._aget_provider_arguments(provider)
        if provider.is_coroutine:
            return await provider.obj(*args, **kwargs)
        return provider.obj(*args, **kwargs)

    def _validate_instance_is_not_resource(self, provider: Provider) -> None:
        if provider.is_resource or provider.is_async_resource:
            raise ProviderError(
                f"The instance for the resource provider `{provider}` cannot be "
                "created until the scope context has been started. Please ensure "
                "that the scope context is started."
            )

    @contextlib.contextmanager
    def override(self, interface: t.Type[T], instance: t.Any) -> t.Iterator[None]:
        if not self.has_provider(interface):
            raise ProviderError(
                f"The provider interface `{get_full_qualname(interface)}` "
                "not registered."
            )
        self._override_instances[interface] = instance
        yield
        del self._override_instances[interface]

    # Decorators

    def provider(
        self, *, scope: Scope, override: bool = False
    ) -> t.Callable[[t.Callable[P, T]], t.Callable[P, T]]:
        def decorator(func: t.Callable[P, T]) -> t.Callable[P, T]:
            interface = self._get_provider_annotation(func)
            self.register_provider(interface, func, scope=scope, override=override)
            return func

        return decorator

    @t.overload
    def inject(self, obj: t.Callable[P, T]) -> t.Callable[P, T]:
        ...

    @t.overload
    def inject(
        self, obj: t.Callable[P, t.Awaitable[T]]
    ) -> t.Callable[P, t.Awaitable[T]]:
        ...

    @t.overload
    def inject(
        self,
    ) -> t.Callable[
        [t.Callable[P, t.Union[T, t.Awaitable[T]]]],
        t.Callable[P, t.Union[T, t.Awaitable[T]]],
    ]:
        ...

    def inject(
        self,
        obj: t.Union[t.Callable[P, t.Union[T, t.Awaitable[T]]], None] = None,
    ) -> t.Union[
        t.Callable[
            [t.Callable[P, t.Union[T, t.Awaitable[T]]]],
            t.Callable[P, t.Union[T, t.Awaitable[T]]],
        ],
        t.Callable[P, t.Union[T, t.Awaitable[T]]],
    ]:
        def decorator(
            obj: t.Callable[P, t.Union[T, t.Awaitable[T]]]
        ) -> t.Callable[P, t.Union[T, t.Awaitable[T]]]:
            injected_params = self._get_injected_params(obj)

            if inspect.iscoroutinefunction(obj):

                @wraps(obj)
                async def awrapped(*args: P.args, **kwargs: P.kwargs) -> T:
                    for name, annotation in injected_params.items():
                        kwargs[name] = await self.aget_instance(annotation)
                    return t.cast(T, await obj(*args, **kwargs))

                return awrapped

            @wraps(obj)
            def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
                for name, annotation in injected_params.items():
                    kwargs[name] = self.get_instance(annotation)
                return t.cast(T, obj(*args, **kwargs))

            return wrapped

        if obj is None:
            return decorator
        return decorator(obj)

    # Scanner

    def scan(
        self,
        /,
        packages: t.Union[
            t.Union[types.ModuleType, str],
            t.Iterable[t.Union[types.ModuleType, str]],
        ],
        *,
        tags: t.Optional[t.Iterable[str]] = None,
    ) -> None:
        dependencies: t.List[ScannedDependency] = []

        if isinstance(packages, t.Iterable) and not isinstance(packages, str):
            scan_packages: t.Iterable[t.Union[types.ModuleType, str]] = packages
        else:
            scan_packages = t.cast(
                t.Iterable[t.Union[types.ModuleType, str]], [packages]
            )

        for package in scan_packages:
            dependencies.extend(self._scan_package(package, tags=tags))

        for dependency in dependencies:
            decorator = self.inject()(dependency.member)
            setattr(dependency.module, dependency.member.__name__, decorator)

    def _scan_package(
        self,
        package: t.Union[types.ModuleType, str],
        *,
        tags: t.Optional[t.Iterable[str]] = None,
    ) -> t.List[ScannedDependency]:
        tags = tags or []
        if isinstance(package, str):
            package = importlib.import_module(package)

        package_path = getattr(package, "__path__", None)

        if not package_path:
            return self._scan_module(package, tags=tags)

        dependencies: t.List[ScannedDependency] = []

        for module_info in pkgutil.walk_packages(
            path=package_path, prefix=package.__name__ + "."
        ):
            module = importlib.import_module(module_info.name)
            dependencies.extend(self._scan_module(module, tags=tags))

        return dependencies

    def _scan_module(
        self,
        module: types.ModuleType,
        *,
        tags: t.Iterable[str],
    ) -> t.List[ScannedDependency]:
        dependencies: t.List[ScannedDependency] = []

        for _, member in inspect.getmembers(module):
            if getattr(member, "__module__", None) != module.__name__ or not callable(
                member
            ):
                continue

            member_tags = getattr(member, "__pyxdi_tags__", [])
            if tags and (
                member_tags
                and not set(member_tags).intersection(tags)
                or not member_tags
            ):
                continue

            injected = getattr(member, "__pyxdi_inject__", None)
            if injected:
                dependencies.append(
                    self._create_scanned_dependency(member=member, module=module)
                )
                continue

            # Get by pyxdi.dep mark
            if inspect.isclass(member):
                signature = get_signature(member.__init__)
            else:
                signature = get_signature(member)
            for parameter in signature.parameters.values():
                if isinstance(parameter.default, DependencyMark):
                    dependencies.append(
                        self._create_scanned_dependency(member=member, module=module)
                    )
                    continue

        return dependencies

    def _create_scanned_dependency(
        self, member: t.Any, module: types.ModuleType
    ) -> ScannedDependency:
        if hasattr(member, "__wrapped__"):
            member = member.__wrapped__
        return ScannedDependency(member=member, module=module)

    # Inspection

    def _get_provider_annotation(self, obj: t.Callable[..., t.Any]) -> t.Any:
        annotation = get_signature(obj).return_annotation

        if annotation is inspect._empty:  # noqa
            raise AnnotationError(
                f"Missing `{get_full_qualname(obj)}` provider return annotation."
            )

        origin = get_origin(annotation) or annotation
        args = get_args(annotation)

        # Supported generic types
        if origin in (list, dict, tuple, Annotated):
            if args:
                return annotation
            else:
                raise AnnotationError(
                    f"Cannot use `{get_full_qualname(obj)}` generic type annotation "
                    "without actual type."
                )

        try:
            return args[0]
        except IndexError:
            return annotation

    def _get_provider_arguments(
        self, provider: Provider
    ) -> t.Tuple[t.List[t.Any], t.Dict[str, t.Any]]:
        args, kwargs = [], {}
        for parameter in provider.parameters.values():
            instance = self.get_instance(parameter.annotation)
            if parameter.kind == parameter.POSITIONAL_ONLY:
                args.append(instance)
            else:
                kwargs[parameter.name] = instance
        return args, kwargs

    async def _aget_provider_arguments(
        self, provider: Provider
    ) -> t.Tuple[t.List[t.Any], t.Dict[str, t.Any]]:
        args, kwargs = [], {}
        for parameter in provider.parameters.values():
            instance = await self.aget_instance(parameter.annotation)
            if parameter.kind == parameter.POSITIONAL_ONLY:
                args.append(instance)
            else:
                kwargs[parameter.name] = instance
        return args, kwargs

    def _get_injected_params(self, obj: t.Callable[..., t.Any]) -> t.Dict[str, t.Any]:
        injected_params = {}
        for parameter in get_signature(obj).parameters.values():
            if not isinstance(parameter.default, DependencyMark):
                continue
            self._validate_injected_parameter(obj, parameter)
            injected_params[parameter.name] = parameter.annotation
        return injected_params

    def _validate_injected_parameter(
        self, obj: t.Callable[..., t.Any], parameter: inspect.Parameter
    ) -> None:
        if parameter.annotation is inspect._empty:  # noqa
            raise AnnotationError(
                f"Missing `{get_full_qualname(obj)}` parameter "
                f"`{parameter.name}` annotation."
            )

        if not self.has_provider(parameter.annotation):
            raise UnknownDependencyError(
                f"`{get_full_qualname(obj)}` includes an unrecognized parameter "
                f"`{parameter.name}` with a dependency "
                f"annotation of `{get_full_qualname(parameter.annotation)}`."
            )


class ScopedContext:
    def __init__(self, scope: Scope, root: PyxDI) -> None:
        self._scope = scope
        self._root = root
        self._instances: t.Dict[t.Type[t.Any], t.Any] = {}
        self._stack = contextlib.ExitStack()
        self._async_stack = contextlib.AsyncExitStack()

    def get(self, interface: t.Type[T]) -> T:
        instance = self._instances.get(interface)
        if instance is None:
            provider = self._root.get_provider(interface)
            if provider.is_resource:
                instance = self._root.create_resource(provider, stack=self._stack)
            else:
                instance = self._root.create_instance(provider)
            self._instances[interface] = instance
        return t.cast(T, instance)

    async def aget(self, interface: t.Type[T]) -> T:
        instance = self._instances.get(interface)
        if instance is None:
            provider = self._root.get_provider(interface)
            if provider.is_resource:
                instance = await run_async(
                    self._root.create_resource, provider, stack=self._stack
                )
            elif provider.is_async_resource:
                instance = await self._root.acreate_resource(
                    provider, stack=self._async_stack
                )
            else:
                instance = await self._root.acreate_instance(provider)
            self._instances[interface] = instance
        return t.cast(T, instance)

    def has(self, interface: t.Type[t.Any]) -> bool:
        return interface in self._instances

    def delete(self, interface: t.Type[t.Any]) -> None:
        self._instances.pop(interface, None)

    def start(self) -> None:
        """Scope Context start event."""

    def close(self) -> None:
        self._stack.close()

    async def astart(self) -> None:
        """Scope Context start asynchronous event."""

    async def aclose(self) -> None:
        await run_async(self._stack.close)
        await self._async_stack.aclose()

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: t.Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        self.close()
        return

    async def __aenter__(self) -> Self:
        await self.astart()
        return self

    async def __aexit__(
        self,
        exc_type: t.Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        await self.aclose()
        return


@t.final
class SingletonContext(ScopedContext):
    def __init__(self, root: PyxDI):
        super().__init__("singleton", root)

    def start(self) -> None:
        for interface, provider in self._iter_providers():
            if provider.is_resource:
                self._instances[interface] = self._root.create_resource(
                    provider, stack=self._stack
                )
            elif provider.is_async_resource:
                raise ProviderError(
                    f"The provider `{provider}` cannot be started in synchronous mode "
                    "because it is an asynchronous provider. Please start the provider "
                    "in asynchronous mode before using it."
                )

    async def astart(self) -> None:
        for interface, provider in self._iter_providers():
            if provider.is_resource:
                self._instances[interface] = await run_async(
                    self._root.create_resource, provider, stack=self._stack
                )
            elif provider.is_async_resource:
                self._instances[interface] = await self._root.acreate_resource(
                    provider, stack=self._async_stack
                )

    def _iter_providers(self) -> t.Iterator[t.Tuple[t.Type[t.Any], Provider]]:
        for interface, provider in self._root.providers.items():
            if provider.scope == self._scope:
                yield interface, provider


@t.final
class RequestContext(ScopedContext):
    def __init__(self, root: PyxDI):
        super().__init__("request", root)


class ModuleMeta(type):
    def __new__(
        cls,
        name: str,
        bases: t.Tuple[type, ...],
        attrs: t.Dict[str, t.Any],
    ) -> t.Any:
        attrs["providers"] = [
            (name, getattr(value, "__pyxdi_provider__", {}))
            for name, value in attrs.items()
            if hasattr(value, "__pyxdi_provider__")
        ]
        return super().__new__(cls, name, bases, attrs)


class Module(metaclass=ModuleMeta):
    """
    Module base class.
    """

    providers: t.List[t.Tuple[str, t.Dict[str, t.Any]]]

    def configure(self, di: PyxDI) -> None:
        ...
