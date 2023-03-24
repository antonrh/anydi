from __future__ import annotations

import contextlib
import functools
import importlib
import inspect
import logging
import pkgutil
import typing as t
import uuid
from collections import defaultdict
from contextvars import ContextVar
from dataclasses import dataclass
from functools import cached_property, partial
from types import ModuleType, TracebackType

try:
    from types import NoneType
except ImportError:
    NoneType = type(None)  # type: ignore[assignment,misc]

import anyio

from .exceptions import (
    AnnotationError,
    InvalidScope,
    ProviderError,
    ScopeMismatch,
    UnknownDependency,
)
from .types import InterfaceT, ProviderObj, Scope
from .utils import get_qualname

logger = logging.getLogger(__name__)

ALLOWED_SCOPES: t.Dict[Scope, t.List[Scope]] = {
    "singleton": ["singleton"],
    "request": ["request", "singleton"],
    "transient": ["transient", "singleton", "request"],
}


@dataclass(frozen=True)
class Provider:
    obj: ProviderObj
    scope: Scope

    def __str__(self) -> str:
        return self.name

    @cached_property
    def name(self) -> str:
        return get_qualname(self.obj)

    @cached_property
    def is_class(self) -> bool:
        return inspect.isclass(self.obj)

    @cached_property
    def is_function(self) -> bool:
        return inspect.isfunction(self.obj) and not (
            self.is_resource or self.is_async_resource
        )

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
class ScannedProvider:
    member: t.Any
    scope: Scope


@dataclass(frozen=True)
class ScannedDependency:
    member: t.Any
    module: ModuleType


class DependencyMark:
    __slots__ = ()


def Dependency() -> t.Any:  # noqa
    return DependencyMark()


@dataclass(frozen=True)
class UnresolvedDependency:
    parameter_name: str
    obj: t.Callable[..., t.Any]


class PyxDI:
    def __init__(
        self,
        *,
        default_scope: Scope = "singleton",
        auto_register: bool = False,
    ) -> None:
        self._default_scope = default_scope
        self._auto_register = auto_register
        self._providers: t.Dict[t.Type[t.Any], Provider] = {}
        self._singleton_context = ScopedContext("singleton", self)
        self._request_context_var: ContextVar[t.Optional[ScopedContext]] = ContextVar(
            "request_context", default=None
        )
        self._unresolved_providers: t.Dict[
            t.Type[t.Any], t.List[UnresolvedProvider]
        ] = defaultdict(list)
        self._unresolved_dependencies: t.Dict[t.Type[t.Any], UnresolvedDependency] = {}
        self._signature_cache: t.Dict[t.Callable[..., t.Any], inspect.Signature] = {}

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
        obj: ProviderObj,
        *,
        scope: t.Optional[Scope] = None,
        override: bool = False,
        ignore: bool = False,
    ) -> Provider:
        provider = Provider(obj=obj, scope=scope or self.default_scope)

        if (provider.is_resource or provider.is_async_resource) and (
            interface is NoneType or interface is None
        ):
            interface = type(f"EventResource_{uuid.uuid4()}", (), {})

        try:
            registered_provider = self.get_provider(interface)
        except ProviderError:
            pass
        else:
            if override:
                self._providers[interface] = provider
                return provider

            if ignore:
                logger.info(
                    f"Ignoring the `{provider}` provider as it "
                    "has already been registered."
                )
                return registered_provider

            raise ProviderError(
                f"The provider interface `{get_qualname(interface)}` "
                "already registered."
            )

        self._validate_provider_scope(provider)
        self._validate_provider_type(provider)
        self._validate_provider_match_scopes(interface, provider)

        self._providers[interface] = provider
        return provider

    def unregister_provider(self, interface: t.Type[t.Any]) -> None:
        if not self.has_provider(interface):
            raise ProviderError(
                f"The provider interface `{get_qualname(interface)}` not registered."
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
        try:
            return self._providers[interface]
        except KeyError:
            raise ProviderError(
                f"The provider interface for `{get_qualname(interface)}` has not been "
                "registered. Please ensure that the provider interface is properly "
                "registered before attempting to use it."
            )

    def singleton(
        self, interface: t.Type[InterfaceT], instance: t.Any, *, override: bool = False
    ) -> Provider:
        return self.register_provider(
            interface, lambda: instance, scope="singleton", override=override
        )

    # Validators
    def _validate_provider_scope(self, provider: Provider) -> None:
        if provider.scope not in t.get_args(Scope):
            raise InvalidScope(
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

        for parameter in self._get_signature(obj).parameters.values():
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
                raise ScopeMismatch(
                    f"The provider `{get_qualname(obj)}` with a {scope} scope was "
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
                    provider_name = get_qualname(unresolved_provider.provider.obj)
                    errors.append(
                        f"- `{provider_name}` has unknown `{parameter_name}: "
                        f"{get_qualname(unresolved_interface)}` parameter"
                    )
            message = "\n".join(errors)
            raise UnknownDependency(
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
                    f"- `{get_qualname(dependency.obj)}` has unknown "
                    f"`{parameter_name}: {get_qualname(unresolved_interface)}` "
                    f"injected parameter"
                )
            if not errors:
                return
            message = "\n".join(errors)
            raise UnknownDependency(
                "The following unknown injected dependencies were detected:"
                f"\n{message}."
            )

    # Lifespan

    def start(self) -> None:
        self.validate()
        self._singleton_context.start()

    def close(self) -> None:
        self._singleton_context.close()

    def request_context(
        self,
    ) -> t.ContextManager["ScopedContext"]:
        return contextlib.contextmanager(self._request_context)()

    def _request_context(self) -> t.Iterator["ScopedContext"]:
        with self.create_request_context() as context:
            token = self._request_context_var.set(context)
            yield context
            self._request_context_var.reset(token)

    # Asynchronous lifespan

    async def astart(self) -> None:
        self.validate()
        await self._singleton_context.astart()

    async def aclose(self) -> None:
        await self._singleton_context.aclose()

    async def arequest_context(
        self,
    ) -> t.AsyncContextManager["ScopedContext"]:
        return contextlib.asynccontextmanager(self._arequest_context)()

    async def _arequest_context(self) -> t.AsyncIterator["ScopedContext"]:
        async with self.create_request_context() as context:
            token = self._request_context_var.set(context)
            yield context
            self._request_context_var.reset(token)

    def create_request_context(self) -> "ScopedContext":
        return ScopedContext("request", self)

    def _get_request_context(self) -> "ScopedContext":
        request_context = self._request_context_var.get()
        if request_context is None:
            raise LookupError(
                "The request context has not been started. Please ensure that "
                "the request context is properly initialized before attempting "
                "to use it."
            )
        return request_context

    # Instance

    def get(self, interface: t.Type[InterfaceT]) -> InterfaceT:
        try:
            provider = self.get_provider(interface)
        except ProviderError as exc:
            if self.auto_register and inspect.isclass(interface):
                try:
                    self._get_signature(interface)
                except ValueError:
                    raise exc
                scope = getattr(interface, "__pyxdi_scope__", self._default_scope)
                provider = self.register_provider(interface, interface, scope=scope)
            else:
                raise

        scoped_context = self._get_scoped_context(provider.scope)
        if scoped_context:
            return scoped_context.get(interface)

        return t.cast(InterfaceT, self.create_instance(provider))

    def has(self, interface: t.Type[InterfaceT]) -> bool:
        try:
            provider = self.get_provider(interface)
        except ProviderError:
            return False
        scoped_context = self._get_scoped_context(provider.scope)
        if scoped_context:
            return scoped_context.has(interface)
        return True

    def _get_scoped_context(self, scope: Scope) -> t.Optional["ScopedContext"]:
        if scope == "singleton":
            return self._singleton_context
        elif scope == "request":
            request_context = self._get_request_context()
            return request_context
        return None

    @contextlib.contextmanager
    def override(
        self, interface: t.Type[InterfaceT], instance: t.Any
    ) -> t.Iterator[None]:
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
        args, kwargs = self._get_provider_arguments(provider)
        cm = contextlib.asynccontextmanager(provider.obj)(*args, **kwargs)
        return await stack.enter_async_context(cm)

    def create_instance(self, provider: Provider) -> t.Any:
        if provider.is_resource or provider.is_async_resource:
            raise ProviderError(
                f"The instance for the resource provider `{provider}` cannot be "
                "created until the scope context has been started. Please ensure "
                "that the scope context is started."
            )
        args, kwargs = self._get_provider_arguments(provider)
        return provider.obj(*args, **kwargs)

    # Decorators

    @t.overload
    def provider(
        self,
        func: None = ...,
        *,
        scope: t.Optional[Scope] = None,
        override: bool = False,
        ignore: bool = False,
    ) -> t.Callable[..., t.Any]:
        ...

    @t.overload
    def provider(
        self,
        func: ProviderObj,
        *,
        scope: t.Optional[Scope] = None,
        override: bool = False,
        ignore: bool = False,
    ) -> t.Callable[[ProviderObj], t.Any]:
        ...

    def provider(
        self,
        func: t.Union[ProviderObj, None] = None,
        *,
        scope: t.Optional[Scope] = None,
        override: bool = False,
        ignore: bool = False,
    ) -> t.Union[ProviderObj, t.Callable[[Provider], t.Any]]:
        decorator = self._provider_decorator(
            scope=scope, override=override, ignore=ignore
        )
        if func is None:
            return decorator
        return decorator(func)  # type: ignore[no-any-return]

    def _provider_decorator(
        self,
        *,
        scope: t.Optional[Scope] = None,
        override: bool = False,
        ignore: bool = False,
    ) -> t.Callable[[ProviderObj], t.Any]:
        def register_provider(func: ProviderObj) -> t.Any:
            interface = self._get_provider_annotation(func)
            self.register_provider(
                interface,
                func,
                scope=scope,
                override=override,
                ignore=ignore,
            )
            return func

        return register_provider

    def inject(self, obj: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        injected_params = self._get_injectable_params(obj)

        if inspect.iscoroutinefunction(obj):

            @functools.wraps(obj)
            async def awrapped(*args: t.Any, **kwargs: t.Any) -> t.Any:
                for name, annotation in injected_params.items():
                    kwargs[name] = self.get(annotation)
                return await obj(*args, **kwargs)

            return awrapped

        @functools.wraps(obj)
        def wrapped(*args: t.Any, **kwargs: t.Any) -> t.Any:
            for name, annotation in injected_params.items():
                kwargs[name] = self.get(annotation)
            return obj(*args, **kwargs)

        return wrapped

    # Scanner

    def scan(
        self,
        /,
        packages: t.Union[
            t.Union[ModuleType, str],
            t.Iterable[t.Union[ModuleType, str]],
        ],
        *,
        tags: t.Optional[t.Iterable[str]] = None,
    ) -> None:
        scanned_providers: t.List[ScannedProvider] = []
        scanned_dependencies: t.List[ScannedDependency] = []

        if isinstance(packages, t.Iterable) and not isinstance(packages, str):
            scan_packages: t.Iterable[t.Union[ModuleType, str]] = packages
        else:
            scan_packages = t.cast(t.Iterable[t.Union[ModuleType, str]], [packages])

        for package in scan_packages:
            _scanned_providers, _scanned_dependencies = self._scan_package(
                package, tags=tags
            )
            scanned_providers.extend(_scanned_providers)
            scanned_dependencies.extend(_scanned_dependencies)

        for scanned_provider in scanned_providers:
            self.provider(
                func=scanned_provider.member,
                scope=scanned_provider.scope,
                override=False,
                ignore=True,
            )

        for scanned_dependency in scanned_dependencies:
            decorator = self.inject(scanned_dependency.member)
            setattr(
                scanned_dependency.module,
                scanned_dependency.member.__name__,
                decorator,
            )

    def _scan_package(
        self,
        package: t.Union[ModuleType, str],
        *,
        tags: t.Optional[t.Iterable[str]] = None,
    ) -> t.Tuple[t.List[ScannedProvider], t.List[ScannedDependency]]:
        tags = tags or []
        if isinstance(package, str):
            package = importlib.import_module(package)

        package_path = getattr(package, "__path__", None)

        if not package_path:
            return self._scan_module(package, tags=tags)

        scanned_providers: t.List[ScannedProvider] = []
        scanned_dependencies: t.List[ScannedDependency] = []

        for module_info in pkgutil.walk_packages(
            path=package_path, prefix=package.__name__ + "."
        ):
            module = importlib.import_module(module_info.name)
            _scanned_providers, _scanned_dependencies = self._scan_module(
                module, tags=tags
            )
            scanned_providers.extend(_scanned_providers)
            scanned_dependencies.extend(_scanned_dependencies)

        return scanned_providers, scanned_dependencies

    def _scan_module(
        self,
        module: ModuleType,
        *,
        tags: t.Iterable[str],
    ) -> t.Tuple[t.List[ScannedProvider], t.List[ScannedDependency]]:
        scanned_providers: t.List[ScannedProvider] = []
        scanned_dependencies: t.List[ScannedDependency] = []

        for name, member in inspect.getmembers(module):
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

            provided = getattr(member, "__pyxdi_provider__", None)
            if provided:
                scope = provided["scope"]
                scanned_providers.append(ScannedProvider(member=member, scope=scope))
                continue

            injected = getattr(member, "__pyxdi_inject__", None)
            if injected:
                scanned_dependencies.append(
                    self._scanned_dependency(member=member, module=module)
                )
                continue

            # Get by pyxdi.dep mark
            if inspect.isclass(member):
                signature = self._get_signature(member.__init__)
            else:
                signature = self._get_signature(member)
            for parameter in signature.parameters.values():
                if isinstance(parameter.default, DependencyMark):
                    scanned_dependencies.append(
                        self._scanned_dependency(member=member, module=module)
                    )
                    continue

        return scanned_providers, scanned_dependencies

    def _scanned_dependency(
        self, member: t.Any, module: ModuleType
    ) -> ScannedDependency:
        if hasattr(member, "__wrapped__"):
            member = member.__wrapped__
        return ScannedDependency(member=member, module=module)

    # Inspection

    def _get_provider_annotation(self, obj: ProviderObj) -> t.Any:
        annotation = self._get_signature(obj).return_annotation

        if annotation is inspect._empty:  # noqa
            raise AnnotationError(
                f"Missing `{get_qualname(obj)}` provider return annotation."
            )

        origin = t.get_origin(annotation) or annotation
        args = t.get_args(annotation)

        # Supported generic types
        if origin in (list, dict, tuple):
            if args:
                return annotation
            else:
                raise AnnotationError(
                    f"Cannot use `{get_qualname(obj)}` generic type annotation "
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
        signature = self._get_signature(provider.obj)
        for parameter in signature.parameters.values():
            instance = self.get(parameter.annotation)
            if parameter.kind == parameter.POSITIONAL_ONLY:
                args.append(instance)
            else:
                kwargs[parameter.name] = instance
        return args, kwargs

    def _get_injectable_params(self, obj: t.Callable[..., t.Any]) -> t.Dict[str, t.Any]:
        signature = self._get_signature(obj)
        parameters = signature.parameters
        params = {}
        for parameter in parameters.values():
            annotation = parameter.annotation
            if annotation is inspect._empty:  # noqa
                raise AnnotationError(
                    f"Missing `{get_qualname(obj)}` parameter annotation."
                )

            if not isinstance(parameter.default, DependencyMark):
                continue

            if (
                not self.has_provider(annotation)
                and annotation not in self._unresolved_providers
                and annotation not in self._unresolved_dependencies
            ):
                self._unresolved_dependencies[annotation] = UnresolvedDependency(
                    parameter_name=parameter.name, obj=obj
                )

            params[parameter.name] = annotation
        return params

    def _get_signature(self, obj: t.Callable[..., t.Any]) -> inspect.Signature:
        signature = self._signature_cache.get(obj)
        if signature is None:
            signature = inspect.signature(obj)
            self._signature_cache[obj] = signature
        return signature


class ScopedContext:
    def __init__(self, scope: Scope, root: PyxDI) -> None:
        self._scope = scope
        self._root = root
        self._instances: t.Dict[t.Type[t.Any], t.Any] = {}
        self._stack = contextlib.ExitStack()
        self._async_stack = contextlib.AsyncExitStack()

    def get(self, interface: t.Type[InterfaceT]) -> InterfaceT:
        instance = self._instances.get(interface)
        if instance is None:
            provider = self._root.get_provider(interface)
            if provider.is_resource:
                instance = self._root.create_resource(provider, stack=self._stack)
            else:
                instance = self._root.create_instance(provider)
            self._instances[interface] = instance
        return t.cast(InterfaceT, instance)

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
        for interface, provider in self._iter_providers():
            if provider.is_resource:
                instance = self._root.create_resource(provider, stack=self._stack)
                self.set(interface, instance)
            elif provider.is_async_resource:
                raise ProviderError(
                    f"The provider `{provider}` cannot be started in synchronous mode "
                    "because it is an asynchronous provider. Please start the provider "
                    "in asynchronous mode before using it."
                )

    def close(self) -> None:
        self._stack.close()

    async def astart(self) -> None:
        for interface, provider in self._iter_providers():
            if provider.is_resource:
                instance = await anyio.to_thread.run_sync(
                    partial(self._root.create_resource, provider, stack=self._stack)
                )
                self.set(interface, instance)
            elif provider.is_async_resource:
                instance = await self._root.acreate_resource(
                    provider, stack=self._async_stack
                )
                self.set(interface, instance)

    async def aclose(self) -> None:
        await self._async_stack.aclose()
        await anyio.to_thread.run_sync(self._stack.close)

    def __enter__(self) -> ScopedContext:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: t.Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()
        return

    async def __aenter__(self) -> ScopedContext:
        await self.astart()
        return self

    async def __aexit__(
        self,
        exc_type: t.Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.aclose()
        return

    def _iter_providers(self) -> t.Iterator[t.Tuple[t.Type[t.Any], Provider]]:
        for interface, provider in self._root.providers.items():
            if provider.scope == self._scope:
                yield interface, provider
