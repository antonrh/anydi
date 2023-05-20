from __future__ import annotations

import contextlib
import importlib
import inspect
import pkgutil
import types
import typing as t
import uuid
from collections import defaultdict
from contextvars import ContextVar
from dataclasses import dataclass
from functools import cached_property, wraps

from typing_extensions import Annotated, ParamSpec, Self

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
from .utils import (
    get_full_qualname,
    get_signature,
    is_builtin_type,
    make_lazy,
    run_async,
)

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
class UnresolvedProvider:
    interface: t.Type[t.Any]
    parameter_name: str
    provider: Provider


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


@dataclass(frozen=True)
class UnresolvedDependency:
    parameter_name: str
    obj: t.Callable[..., t.Any]


@t.final
class PyxDI:
    def __init__(
        self,
        *,
        default_scope: Scope = "singleton",
        auto_register: bool = False,
        modules: t.Optional[
            t.Sequence[t.Union[Module, t.Type[Module], t.Callable[[PyxDI], None]]],
        ] = None,
    ) -> None:
        self._default_scope = default_scope
        self._auto_register = auto_register
        self._providers: t.Dict[t.Type[t.Any], Provider] = {}
        self._singleton_context = SingletonContext(self)
        self._request_context_var: ContextVar[t.Optional[RequestContext]] = ContextVar(
            "request_context", default=None
        )
        self._unresolved_providers: t.Dict[
            t.Type[t.Any], t.List[UnresolvedProvider]
        ] = defaultdict(list)
        self._unresolved_dependencies: t.Dict[t.Type[t.Any], UnresolvedDependency] = {}

        # Register modules
        modules = modules or []
        for module in modules:
            self.register_module(module)

    @property
    def default_scope(self) -> Scope:
        return self._default_scope

    @property
    def auto_register(self) -> bool:
        return self._auto_register

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
        scope: t.Optional[Scope] = None,
        override: bool = False,
    ) -> Provider:
        provider = Provider(obj=obj, scope=scope or self.default_scope)

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
        self._unresolved_providers.pop(interface, None)
        self._unresolved_dependencies.pop(interface, None)

    def get_provider(self, interface: t.Type[t.Any]) -> Provider:
        """
        Get provider by interface.
        """
        try:
            return self._providers[interface]
        except KeyError as exc:
            # Try to auto register instance class, or raise ProviderError
            if (
                self.auto_register
                and inspect.isclass(interface)
                and not is_builtin_type(interface)
            ):
                scope = getattr(interface, "__pyxdi_scope__", self.default_scope)
                return self.register_provider(interface, interface, scope=scope)
            raise ProviderError(
                f"The provider interface for `{get_full_qualname(interface)}` has "
                "not been registered. Please ensure that the provider interface is "
                "properly registered before attempting to use it."
            ) from exc

    def singleton(
        self, interface: t.Type[t.Any], instance: t.Any, *, override: bool = False
    ) -> Provider:
        """
        Register singleton instance provider.
        """
        return self.register_provider(
            interface, lambda: instance, scope="singleton", override=override
        )

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

        obj, scope = provider.obj, provider.scope

        for parameter in get_signature(obj).parameters.values():
            if parameter.annotation is inspect._empty:  # noqa
                raise AnnotationError(
                    f"Missing provider `{provider}` "
                    f"dependency `{parameter.name}` annotation."
                )
            try:
                sub_provider = self.get_provider(parameter.annotation)
                related_providers.append((sub_provider, True))
            except ProviderError:
                self._unresolved_providers[parameter.annotation].append(
                    UnresolvedProvider(
                        interface=interface,
                        parameter_name=parameter.name,
                        provider=provider,
                    )
                )

        for unresolved_provider in self._unresolved_providers.pop(interface, []):
            sub_provider = self.get_provider(unresolved_provider.interface)
            related_providers.append((sub_provider, False))

        for related_provider, direct in related_providers:
            if direct:
                left_scope, right_scope = related_provider.scope, scope
            else:
                left_scope, right_scope = scope, related_provider.scope
            allowed_scopes = ALLOWED_SCOPES.get(right_scope) or []
            if left_scope not in allowed_scopes:
                raise ScopeMismatchError(
                    f"The provider `{get_full_qualname(obj)}` with a {scope} scope was "
                    f"attempted to be registered with the provider "
                    f"`{related_provider}` with a `{related_provider.scope}` scope, "
                    f"which is not allowed. Please ensure that all providers are "
                    f"registered with matching scopes."
                )

    def validate(self) -> None:
        if self._unresolved_providers:
            errors = []
            for (
                unresolved_interface,
                unresolved_providers,
            ) in self._unresolved_providers.items():
                for unresolved_provider in unresolved_providers:
                    parameter_name = unresolved_provider.parameter_name
                    provider_name = get_full_qualname(unresolved_provider.provider.obj)
                    errors.append(
                        f"- `{provider_name}` has unknown `{parameter_name}: "
                        f"{get_full_qualname(unresolved_interface)}` parameter"
                    )
            message = "\n".join(errors)
            raise UnknownDependencyError(
                "The following unknown provided dependencies were detected:"
                f"\n{message}."
            )
        if self._unresolved_dependencies:
            errors = []
            for (
                unresolved_interface,
                dependency,
            ) in self._unresolved_dependencies.items():
                if inspect.isclass(unresolved_interface) and self.auto_register:
                    continue
                parameter_name = dependency.parameter_name
                errors.append(
                    f"- `{get_full_qualname(dependency.obj)}` has unknown "
                    f"`{parameter_name}: {get_full_qualname(unresolved_interface)}` "
                    f"injected parameter"
                )
            if not errors:
                return
            message = "\n".join(errors)
            raise UnknownDependencyError(
                "The following unknown injected dependencies were detected:"
                f"\n{message}."
            )

    # Modules
    def register_module(
        self, module: t.Union[Module, t.Type[Module], t.Callable[[PyxDI], None]]
    ) -> None:
        """
        Register module as callable, Module type or Module instance.
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
            for _, method in inspect.getmembers(module):
                provided = getattr(method, "__pyxdi_provider__", None)
                if not provided:
                    continue
                scope = provided.get("scope")
                self.provider(scope=scope, override=True)(method)

    # Lifespan

    def start(self) -> None:
        self.validate()
        self._singleton_context.start()

    def close(self) -> None:
        self._singleton_context.close()

    def request_context(
        self,
    ) -> t.ContextManager[RequestContext]:
        return contextlib.contextmanager(self._request_context)()

    def _request_context(self) -> t.Iterator[RequestContext]:
        context = RequestContext(self)
        token = self._request_context_var.set(context)
        with context:
            yield context
            self._request_context_var.reset(token)

    # Asynchronous lifespan

    async def astart(self) -> None:
        self.validate()
        await self._singleton_context.astart()

    async def aclose(self) -> None:
        await self._singleton_context.aclose()

    def arequest_context(
        self,
    ) -> t.AsyncContextManager[RequestContext]:
        return contextlib.asynccontextmanager(self._arequest_context)()

    async def _arequest_context(self) -> t.AsyncIterator[RequestContext]:
        context = RequestContext(self)
        token = self._request_context_var.set(context)
        async with context:
            yield context
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

    def get(self, interface: t.Type[T]) -> T:
        """
        Get instance by interface.
        """
        provider = self.get_provider(interface)

        scoped_context = self._get_scoped_context(provider.scope)
        if scoped_context:
            return scoped_context.get(interface)

        return t.cast(T, self.create_instance(provider))

    async def aget(self, interface: t.Type[T]) -> T:
        """
        Get instance by interface.
        """
        provider = self.get_provider(interface)

        scoped_context = self._get_scoped_context(provider.scope)
        if scoped_context:
            return await scoped_context.aget(interface)

        return t.cast(T, await self.acreate_instance(provider))

    def has(self, interface: t.Type[T]) -> bool:
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

    @contextlib.contextmanager
    def override(self, interface: t.Type[T], instance: t.Any) -> t.Iterator[None]:
        origin_instance: t.Optional[t.Any] = None
        origin_provider: t.Optional[Provider] = None
        scope = self.default_scope

        if self.has_provider(interface):
            origin_provider = self.get_provider(interface)
            if origin_provider.is_async_resource and not self.has(interface):
                origin_instance = None
            else:
                origin_instance = self.get(interface)
            scope = origin_provider.scope

        provider = self.register_provider(
            interface, lambda: instance, scope=scope, override=True
        )

        scoped_context = self._get_scoped_context(provider.scope)
        if scoped_context:
            scoped_context.set(interface, instance=instance)

        yield

        if origin_provider:
            self.register_provider(
                interface,
                origin_provider.obj,
                scope=origin_provider.scope,
                override=True,
            )
            if origin_instance and scoped_context:
                scoped_context.set(interface, instance=origin_instance)
        else:
            self.unregister_provider(interface)

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

    # Decorators

    @t.overload
    def provider(self, func: t.Callable[P, T]) -> t.Callable[P, T]:
        ...

    @t.overload
    def provider(
        self,
        *,
        scope: t.Optional[Scope] = None,
        override: bool = False,
    ) -> t.Callable[[t.Callable[P, T]], t.Callable[P, T]]:
        ...

    def provider(
        self,
        func: t.Optional[t.Callable[P, T]] = None,
        *,
        scope: t.Optional[Scope] = None,
        override: bool = False,
    ) -> t.Union[t.Callable[P, T], t.Callable[[t.Callable[P, T]], t.Callable[P, T]]]:
        def decorator(func: t.Callable[P, T]) -> t.Callable[P, T]:
            interface = self._get_provider_annotation(func)
            self.register_provider(interface, func, scope=scope, override=override)
            return func

        if func is None:
            return decorator
        return decorator(func)

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
                        kwargs[name] = await self.aget(annotation)
                    return t.cast(T, await obj(*args, **kwargs))

                return awrapped

            @wraps(obj)
            def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
                for name, annotation in injected_params.items():
                    kwargs[name] = make_lazy(self.get, annotation)
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

        origin = t.get_origin(annotation) or annotation
        args = t.get_args(annotation)

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
        args = []
        kwargs = {}
        for parameter in get_signature(provider.obj).parameters.values():
            instance = make_lazy(self.get, parameter.annotation)
            if parameter.kind == parameter.POSITIONAL_ONLY:
                args.append(instance)
            else:
                kwargs[parameter.name] = instance
        return args, kwargs

    async def _aget_provider_arguments(
        self, provider: Provider
    ) -> t.Tuple[t.List[t.Any], t.Dict[str, t.Any]]:
        args = []
        kwargs = {}
        for parameter in get_signature(provider.obj).parameters.values():
            instance = await self.aget(parameter.annotation)
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

            annotation = parameter.annotation
            if annotation is inspect._empty:  # noqa
                raise AnnotationError(
                    f"Missing `{get_full_qualname(obj)}` parameter annotation."
                )

            if (
                not self.has_provider(annotation)
                and annotation not in self._unresolved_providers
                and annotation not in self._unresolved_dependencies
            ):
                self._unresolved_dependencies[annotation] = UnresolvedDependency(
                    parameter_name=parameter.name, obj=obj
                )

            injected_params[parameter.name] = annotation
        return injected_params


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

    def set(self, interface: t.Type[t.Any], instance: t.Any) -> None:
        self._instances[interface] = instance
        self._root.register_provider(
            interface, lambda: interface, scope=self._scope, override=True
        )

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


class Module:
    """
    Module base class.
    """

    def configure(self, di: PyxDI) -> None:
        ...
