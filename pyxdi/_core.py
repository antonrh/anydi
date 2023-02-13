from __future__ import annotations

import abc
import contextlib
import inspect
import typing as t
from collections import defaultdict
from contextvars import ContextVar
from dataclasses import dataclass
from types import TracebackType

from ._contstants import DEFAULT_SCOPE
from ._exceptions import InvalidMode, InvalidScope, ProviderAlreadyBound, ScopeMismatch
from ._types import InterfaceT, Mode, Provider, Scope

ALLOWED_SCOPES: t.Dict[Scope, t.List[Scope]] = {
    "singleton": ["singleton"],
    "request": ["request", "singleton"],
    "transient": ["transient", "singleton", "request"],
}


class DependencyMarker:
    __slots__ = ()


@dataclass(frozen=True)
class Binding:
    dependency: Provider
    scope: Scope


class BaseDI(abc.ABC):
    mode: t.ClassVar[Mode]

    def __init__(self, default_scope: t.Optional[Scope] = None) -> None:
        self.default_scope = default_scope or DEFAULT_SCOPE
        self.bindings: t.Dict[t.Type[t.Any], Binding] = {}
        self.signature_cache: t.Dict[t.Callable[..., t.Any], inspect.Signature] = {}
        self.lazy_interfaces: t.Dict[
            t.Type[t.Any], t.List[t.Type[t.Any]]
        ] = defaultdict(list)

    def get_binding(self, interface: t.Type[InterfaceT]) -> Binding:
        try:
            return self.bindings[interface]
        except KeyError:
            raise LookupError(
                f"Binding to `{self.get_qualname(interface)}` "
                f"dependency is not registered."
            )

    def has_binding(self, interface: t.Type[InterfaceT]) -> bool:
        return interface in self.bindings

    def bind(
        self,
        interface: t.Type[InterfaceT],
        provider: Provider,
        *,
        scope: t.Optional[Scope] = None,
        override: bool = False,
    ) -> None:
        scope = scope or self.default_scope

        self.ensure_valid_scope(scope)

        if self.has_binding(interface) and not override:
            raise ProviderAlreadyBound(
                f"Provider interface `{self.get_qualname(interface)}` already bound."
            )

        if self.mode == "sync" and (
            inspect.isasyncgenfunction(provider)
            or inspect.iscoroutinefunction(provider)
        ):
            raise InvalidMode(
                f"Cannot bind asynchronous provider "
                f"`{self.get_qualname(provider)}` in `sync` mode."
            )

        self.validate_sub_provider(interface, provider, scope=scope)

        self.bindings[interface] = Binding(dependency=provider, scope=scope)

    def provide(
        self, *, scope: t.Optional[Scope] = None, override: bool = False
    ) -> t.Callable[[Provider], t.Any]:
        def provider_func(provider: Provider) -> t.Any:
            interface = self.get_provider_annotation(provider)
            self.bind(interface, provider, scope=scope, override=override)

        return provider_func

    @staticmethod
    def ensure_valid_scope(scope: Scope) -> None:
        if scope not in t.get_args(Scope):
            raise InvalidScope("Invalid scope.")

    def validate_sub_provider(
        self, interface: t.Type[InterfaceT], provider: Provider, scope: Scope
    ) -> None:
        related_bindings = []

        for parameter in self.get_signature(provider).parameters.values():
            if parameter.annotation is inspect._empty:  # noqa
                raise TypeError(
                    f"Missing dependency `{self.get_qualname(provider)}` provider "
                    f"sub dependency `{parameter.name}` annotation."
                )
            try:
                sub_binding = self.get_binding(parameter.annotation)
                related_bindings.append((sub_binding, True))
            except LookupError:
                self.lazy_interfaces[parameter.annotation].append(interface)

        for lazy_interface in self.lazy_interfaces.pop(interface, []):
            try:
                sub_binding = self.get_binding(lazy_interface)
                related_bindings.append((sub_binding, False))
            except LookupError:
                pass

        for related_binding, direct in related_bindings:
            if direct:
                left_scope, right_scope = related_binding.scope, scope
            else:
                left_scope, right_scope = scope, related_binding.scope
            allowed_scopes = ALLOWED_SCOPES.get(right_scope) or []
            if left_scope not in allowed_scopes:
                raise ScopeMismatch(
                    f"You tried to bind the `{scope}` scoped dependency "
                    f"`{self.get_qualname(provider)}` with "
                    f"a `{related_binding.scope}` scoped "
                    f"{self.get_qualname(related_binding.dependency)}`."
                )

    def get_provider_annotation(self, provider: Provider) -> t.Any:
        annotation = self.get_signature(provider).return_annotation

        if inspect.isclass(provider):
            return annotation

        if annotation is inspect._empty:  # noqa
            raise TypeError(
                f"Missing `{self.get_qualname(provider)}` provider return annotation."
            )

        origin = t.get_origin(annotation)
        args = t.get_args(annotation)

        # Supported generic types
        if origin in (list, dict, tuple):
            if args:
                return annotation
            else:
                raise TypeError(
                    f"Cannot use `{self.get_qualname(provider)}` generic type "
                    f"annotation without actual type."
                )

        try:
            return t.get_args(annotation)[0]
        except IndexError:
            return annotation

    def get_signature(self, obj: t.Callable[..., t.Any]) -> inspect.Signature:
        if (signature := self.signature_cache.get(obj)) is None:
            signature = inspect.signature(obj)
            self.signature_cache[obj] = signature
        return signature

    def get_injectable_params(self, obj: t.Callable[..., t.Any]) -> t.Dict[str, t.Any]:
        signature = self.get_signature(obj)
        parameters = signature.parameters
        params = {}
        for parameter in parameters.values():
            if not isinstance(parameter.default, DependencyMarker):
                continue
            annotation = parameter.annotation
            if annotation is inspect._empty:  # noqa
                raise TypeError(
                    f"Missing `{self.get_qualname(obj)}` parameter annotation."
                )
            params[parameter.name] = annotation
        return params

    @staticmethod
    def get_qualname(obj: t.Any) -> str:
        qualname = obj.__qualname__
        module_name = getattr(obj, "__module__", None)
        if module_name:
            return f"{module_name}.{qualname}".removeprefix("builtins.")
        return str(qualname)


class DI(BaseDI):
    mode = "sync"

    def __init__(self, default_scope: t.Optional[Scope] = None) -> None:
        super().__init__(default_scope)
        self.singleton_context = Context(self, scope="singleton")
        self.request_context_var: ContextVar[Context | None] = ContextVar(
            "request_context", default=None
        )

    def get(self, interface: t.Type[InterfaceT]) -> InterfaceT:
        binding = self.get_binding(interface)

        if binding.scope == "singleton":
            return self.singleton_context.get(interface)

        elif binding.scope == "request":
            request_context = self.request_context_var.get()
            if request_context is None:
                raise LookupError("Request context is not started.")
            return request_context.get(interface)

        # Transient scope
        return t.cast(InterfaceT, self.create_instance(interface))

    def close(self) -> None:
        self.singleton_context.close()
        request_context = self.request_context_var.get()
        if request_context:
            request_context.close()

    @contextlib.contextmanager
    def request_context(self) -> t.Iterator[Context]:
        with Context(di=self, scope="request") as context:
            token = self.request_context_var.set(context)
            yield context
            self.request_context_var.reset(token)

    def inject_callable(self, obj: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        injectable_params = self.get_injectable_params(obj)

        def wrapped(*args: t.Any, **kwargs: t.Any) -> t.Any:
            for name, annotation in injectable_params.items():
                kwargs[name] = self.get(annotation)
            return obj(*args, **kwargs)

        return wrapped

    def create_instance(
        self,
        interface: t.Type[InterfaceT],
        stack: t.Optional[contextlib.ExitStack] = None,
    ) -> t.Any:
        provider = self.get_binding(interface).dependency
        args, kwargs = self.get_provider_arguments(provider)
        if inspect.isgeneratorfunction(provider):
            cm = contextlib.contextmanager(provider)(*args, **kwargs)
            if stack:
                return stack.enter_context(cm)
            with contextlib.ExitStack() as stack:
                return stack.enter_context(cm)
        elif inspect.isfunction(provider):
            return provider(*args, **kwargs)
        return provider

    def get_provider_arguments(
        self, provider: Provider
    ) -> tuple[list[t.Any], dict[str, t.Any]]:
        args = []
        kwargs = {}
        signature = self.get_signature(provider)
        for parameter in signature.parameters.values():
            instance = self.get(parameter.annotation)
            if parameter.kind == parameter.POSITIONAL_ONLY:
                args.append(instance)
            else:
                kwargs[parameter.name] = instance
        return args, kwargs


class Context:
    def __init__(self, di: "DI", scope: Scope) -> None:
        self.di = di
        self.scope = scope
        self.instances: dict[t.Any, t.Any] = {}
        self.stack = contextlib.ExitStack()

    def get(self, interface: t.Type[InterfaceT]) -> InterfaceT:
        if (instance := self.instances.get(interface)) is None:
            instance = self.di.create_instance(interface, stack=self.stack)
            self.instances[interface] = instance
        return t.cast(InterfaceT, instance)

    def set(self, interface: t.Type[InterfaceT], instance: t.Any) -> None:
        self.di.bind(interface, instance, scope=self.scope)

    def close(self) -> None:
        self.stack.close()

    def __enter__(self) -> Context:
        return self

    def __exit__(
        self,
        exc_type: t.Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()
