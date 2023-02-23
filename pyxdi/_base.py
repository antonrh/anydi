from __future__ import annotations

import contextlib
import inspect
import typing as t
from collections import defaultdict
from contextvars import ContextVar
from dataclasses import dataclass
from functools import cached_property, partial
from types import TracebackType

import anyio
import sniffio

from ._exceptions import (
    InvalidProviderType,
    InvalidScope,
    MissingAnnotation,
    NotSupportedAnnotation,
    ProviderAlreadyRegistered,
    ProviderNotRegistered,
    ProviderNotStarted,
    ScopeMismatch,
    UnknownDependency,
)
from ._types import InterfaceT, ProviderCallable, Scope
from ._utils import get_qualname

ALLOWED_SCOPES: t.Dict[Scope, t.List[Scope]] = {
    "singleton": ["singleton"],
    "request": ["request", "singleton"],
    "transient": ["transient", "singleton", "request"],
}


@dataclass(frozen=True)
class Provider:
    scope: Scope
    obj: ProviderCallable

    def __str__(self) -> str:
        return self.name

    @cached_property
    def name(self) -> str:
        return get_qualname(self.obj)

    @cached_property
    def is_simple_func(self) -> bool:
        return inspect.isfunction(self.obj) and not (
            self.is_resource or self.is_resource or self.is_coroutine_func
        )

    @cached_property
    def is_class(self) -> bool:
        return inspect.isclass(self.obj)

    @cached_property
    def is_coroutine_func(self) -> bool:
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


class Dependency:
    __slots__ = ()


def DependencyParam() -> t.Any:  # noqa
    return Dependency()


@dataclass(frozen=True)
class UnresolvedDependency:
    parameter_name: str
    obj: t.Callable[..., t.Any]


class PyxDI:
    def __init__(
        self, default_scope: Scope = "singleton", auto_register: bool = False
    ) -> None:
        self._default_scope = default_scope
        self._auto_register = auto_register
        self._providers: t.Dict[t.Type[t.Any], Provider] = {}
        self._singleton_context = ScopedContext("singleton", self)
        self._request_context_var: ContextVar[t.Optional[ScopedContext]] = ContextVar(
            "request_context", default=None
        )
        self._signature_cache: t.Dict[t.Callable[..., t.Any], inspect.Signature] = {}
        self._unresolved_providers: t.Dict[
            t.Type[t.Any], t.List[UnresolvedProvider]
        ] = defaultdict(list)
        self._unresolved_dependencies: t.Dict[t.Type[t.Any], UnresolvedDependency] = {}

    @property
    def providers(self) -> t.Dict[t.Type[t.Any], Provider]:
        return self._providers

    def register_provider(
        self,
        interface: t.Type[InterfaceT],
        obj: ProviderCallable,
        *,
        scope: t.Optional[Scope] = None,
        override: bool = False,
    ) -> Provider:
        scope = scope or self._default_scope

        if not self._has_valid_scope(scope):
            raise InvalidScope(
                f"Invalid scope. Only {', '.join(t.get_args(Scope))} "
                "scope are supported."
            )

        if not self._has_valid_provider(obj):
            raise InvalidProviderType(
                "Invalid provider type. Only callable providers are allowed."
            )

        if self.has_provider(interface) and not override:
            raise ProviderAlreadyRegistered(
                f"Provider interface `{get_qualname(interface)}` " "already registered."
            )

        provider = Provider(obj=obj, scope=scope)

        self._validate_sub_providers(interface, provider)
        self._providers[interface] = provider

        return provider

    def get_provider(self, interface: t.Type[t.Any]) -> Provider:
        try:
            return self._providers[interface]
        except KeyError:
            raise ProviderNotRegistered(
                f"Provider interface `{get_qualname(interface)}` dependency "
                "is not registered."
            )

    def has_provider(self, interface: t.Type[InterfaceT]) -> bool:
        return interface in self._providers

    def singleton(
        self, interface: t.Type[InterfaceT], instance: t.Any, *, override: bool = False
    ) -> None:
        self._singleton_context.set(interface, instance, override=override)

    @t.overload
    def provider(
        self,
        func: None = ...,
        *,
        scope: Scope | None = None,
        override: bool = False,
    ) -> t.Callable[..., t.Any]:
        ...

    @t.overload
    def provider(
        self,
        func: ProviderCallable,
        *,
        scope: Scope | None = None,
        override: bool = False,
    ) -> t.Callable[[ProviderCallable], t.Any]:
        ...

    def provider(
        self,
        func: t.Union[ProviderCallable, None] = None,
        *,
        scope: Scope | None = None,
        override: bool = False,
    ) -> t.Union[ProviderCallable, t.Callable[[Provider], t.Any]]:
        decorator = self._provider_decorator(scope=scope, override=override)
        if func is None:
            return decorator
        return decorator(func)  # type: ignore[no-any-return]

    def _provider_decorator(
        self, *, scope: t.Optional[Scope] = None, override: bool = False
    ) -> t.Callable[[ProviderCallable], t.Any]:
        def register_provider(func: ProviderCallable) -> t.Any:
            interface = self._get_provider_annotation(func)
            self.register_provider(interface, func, scope=scope, override=override)

        return register_provider

    def get(self, interface: t.Type[InterfaceT]) -> InterfaceT:
        try:
            provider = self.get_provider(interface)
        except ProviderNotRegistered:
            if self._auto_register and inspect.isclass(interface):
                scope = getattr(interface, "__scope__", self._default_scope)
                provider = self.register_provider(interface, interface, scope=scope)
            else:
                raise

        if provider.scope == "singleton":
            return self._singleton_context.get(interface)
        elif provider.scope == "request":
            request_context = self._request_context_var.get()
            if request_context is None:
                raise LookupError("Request context is not started.")
            return request_context.get(interface)

        return t.cast(InterfaceT, self.create_instance(provider))

    def start(self) -> t.Union[None, t.Awaitable[None]]:
        if self._is_async_loop_running:
            return self._singleton_context.astart()
        self._singleton_context.start()
        return None

    def close(self) -> t.Union[None, t.Awaitable[None]]:
        if self._is_async_loop_running:
            return self._singleton_context.aclose()
        self._singleton_context.close()
        return None

    def request_context(
        self,
    ) -> t.Union[
        t.ContextManager["ScopedContext"],
        t.AsyncContextManager["ScopedContext"],
    ]:
        if self._is_async_loop_running:
            return contextlib.asynccontextmanager(self._arequest_context)()
        return contextlib.contextmanager(self._request_context)()

    def _request_context(self) -> t.Iterator["ScopedContext"]:
        with self._create_request_context() as context:
            token = self._request_context_var.set(context)
            yield context
            self._request_context_var.reset(token)

    async def _arequest_context(self) -> t.AsyncIterator["ScopedContext"]:
        async with self._create_request_context() as context:
            token = self._request_context_var.set(context)
            yield context
            self._request_context_var.reset(token)

    def _create_request_context(self) -> "ScopedContext":
        return ScopedContext("request", self)

    def create_resource(
        self, provider: Provider, *, stack: contextlib.ExitStack
    ) -> t.Any:
        if not provider.is_resource:
            raise TypeError(
                f"Invalid provider `{provider}` type. "
                "Only generator provider type is supported."
            )
        args, kwargs = self._get_provider_arguments(provider)
        cm = contextlib.contextmanager(provider.obj)(*args, **kwargs)
        return stack.enter_context(cm)

    async def acreate_resource(
        self,
        provider: Provider,
        *,
        stack: contextlib.AsyncExitStack,
    ) -> t.Any:
        if not provider.is_async_resource:
            raise TypeError(
                f"Invalid provider `{provider}` type. "
                "Only asynchronous generator provider type is supported."
            )
        args, kwargs = self._get_provider_arguments(provider)
        cm = contextlib.asynccontextmanager(provider.obj)(*args, **kwargs)
        return await stack.enter_async_context(cm)

    def create_instance(self, provider: Provider) -> t.Any:
        if not (provider.is_simple_func or provider.is_class):
            raise TypeError(
                f"Invalid provider `{provider}` type. "
                "Only function provider type is supported."
            )
        args, kwargs = self._get_provider_arguments(provider)
        return provider.obj(*args, **kwargs)

    def inject(self, target: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        injectable_params = self._get_injectable_params(target)

        async def wrapped(*args: t.Any, **kwargs: t.Any) -> t.Any:
            for name, annotation in injectable_params.items():
                kwargs[name] = self.get(annotation)
            return await target(*args, **kwargs)

        def sync_wrapped(*args: t.Any, **kwargs: t.Any) -> t.Any:
            for name, annotation in injectable_params.items():
                kwargs[name] = self.get(annotation)
            return target(*args, **kwargs)

        if inspect.iscoroutinefunction(target):
            return wrapped

        return sync_wrapped

    @staticmethod
    def _has_valid_scope(scope: Scope) -> bool:
        return scope in t.get_args(Scope)

    def _has_valid_provider(self, obj: ProviderCallable) -> bool:
        return (
            inspect.isfunction(obj)
            or inspect.isgeneratorfunction(obj)
            or inspect.iscoroutinefunction(obj)
            or inspect.isasyncgenfunction(obj)
            or self._auto_register
            and inspect.isclass(obj)
        )

    def validate(self) -> None:
        if self._unresolved_providers:
            messages = []
            for (
                unresolved_interface,
                unresolved_providers,
            ) in self._unresolved_providers.items():
                for unresolved_provider in unresolved_providers:
                    parameter_name = unresolved_provider.parameter_name
                    provider_name = get_qualname(unresolved_provider.provider.obj)
                    messages.append(
                        f"- `{provider_name}` has unknown `{parameter_name}: "
                        f"{get_qualname(unresolved_interface)}` parameter"
                    )
            message = "\n".join(messages)
            raise UnknownDependency(
                f"Unknown provided dependencies detected:\n{message}."
            )
        if self._unresolved_dependencies:
            messages = []
            for (
                unresolved_interface,
                dependency,
            ) in self._unresolved_dependencies.items():
                parameter_name = dependency.parameter_name
                messages.append(
                    f"- `{get_qualname(dependency.obj)}` has unknown "
                    f"`{parameter_name}: {get_qualname(unresolved_interface)}` "
                    f"injected parameter"
                )
            message = "\n".join(messages)
            raise UnknownDependency(
                f"Unknown injected dependencies detected:\n{message}."
            )

    def _validate_sub_providers(
        self, interface: t.Type[InterfaceT], provider: Provider
    ) -> None:
        related_providers = []

        func, scope = provider.obj, provider.scope

        for parameter in self._get_signature(func).parameters.values():
            if parameter.annotation is inspect._empty:  # noqa
                raise MissingAnnotation(
                    f"Missing provider `{provider}` "
                    f"dependency `{parameter.name}` annotation."
                )
            try:
                sub_provider = self.get_provider(parameter.annotation)
                related_providers.append((sub_provider, True))
            except ProviderNotRegistered:
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
                    f"You tried to register the `{scope}` scoped provider "
                    f"`{get_qualname(func)}` with a `{related_provider.scope}` scoped "
                    f"{related_provider}`."
                )

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

    def _get_provider_annotation(self, obj: ProviderCallable) -> t.Any:
        annotation = self._get_signature(obj).return_annotation

        if annotation is inspect._empty:  # noqa
            raise MissingAnnotation(
                f"Missing `{get_qualname(obj)}` provider return annotation."
            )

        origin = t.get_origin(annotation) or annotation
        args = t.get_args(annotation)

        # Supported generic types
        if origin in (list, dict, tuple):
            if args:
                return annotation
            else:
                raise NotSupportedAnnotation(
                    f"Cannot use `{get_qualname(obj)}` generic type annotation "
                    "without actual type."
                )

        try:
            return args[0]
        except IndexError:
            return annotation

    def _get_injectable_params(self, obj: t.Callable[..., t.Any]) -> t.Dict[str, t.Any]:
        signature = self._get_signature(obj)
        parameters = signature.parameters
        params = {}
        for parameter in parameters.values():
            annotation = parameter.annotation
            if annotation is inspect._empty:  # noqa
                raise MissingAnnotation(
                    f"Missing `{get_qualname(obj)}` parameter annotation."
                )

            if not isinstance(parameter.default, Dependency):
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

    @property
    def _is_async_loop_running(self) -> bool:
        try:
            sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return False
        return True


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
            try:
                provider = self._root.get_provider(interface)
            except ProviderNotRegistered:
                raise
            else:
                if provider.is_resource or provider.is_async_resource:
                    raise ProviderNotStarted(
                        f"Provider for `{provider}` is not started."
                    )
                instance = self._root.create_instance(provider)
                self._instances[interface] = instance
        return t.cast(InterfaceT, instance)

    def set(
        self, interface: t.Type[t.Any], instance: t.Any, *, override: bool = False
    ) -> None:
        if interface in self._instances and not override:
            raise
        self._instances[interface] = instance

    def start(self) -> None:
        for interface, provider in self._iter_providers():
            if provider.is_resource:
                instance = self._root.create_resource(provider, stack=self._stack)
                self.set(interface, instance)
            elif provider.is_async_resource:
                raise InvalidProviderType(
                    f"Cannot start asynchronous provider `{provider}` "
                    "in synchronous mode."
                )

    def close(self) -> None:
        self._stack.close()

    async def astart(self) -> None:
        for interface, provider in self._iter_providers():
            if provider.is_resource:
                instance = await anyio.to_thread.run_sync(
                    partial(
                        self._root.create_resource,
                        provider,
                        stack=self._stack,
                    )
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
