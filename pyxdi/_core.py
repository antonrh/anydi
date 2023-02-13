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
from ._exceptions import (
    InvalidMode,
    InvalidProviderType,
    InvalidScope,
    MissingProviderAnnotation,
    ProviderAlreadyBound,
    ScopeMismatch,
    UnknownProviderDependency,
)
from ._types import InterfaceT, Mode, Provider, Scope

ALLOWED_SCOPES: t.Dict[Scope, t.List[Scope]] = {
    "singleton": ["singleton"],
    "request": ["request", "singleton"],
    "transient": ["transient", "singleton", "request"],
}


class Dependency:
    __slots__ = ()


@dataclass(frozen=True)
class Binding:
    provider: Provider
    scope: Scope


@dataclass(frozen=True)
class LazyBinding:
    interface: t.Type[t.Any]
    parameter_name: str
    binding: Binding


class BaseDI(abc.ABC):
    mode: t.ClassVar[Mode]

    def __init__(self, default_scope: t.Optional[Scope] = None) -> None:
        self.default_scope = default_scope or DEFAULT_SCOPE
        self.bindings: t.Dict[t.Type[t.Any], Binding] = {}
        self.signature_cache: t.Dict[t.Callable[..., t.Any], inspect.Signature] = {}
        self.lazy_bindings: t.Dict[t.Type[t.Any], t.List[LazyBinding]] = defaultdict(
            list
        )

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

        if not self.has_valid_scope(scope):
            raise InvalidScope(
                f"Invalid scope. Only {', '.join(t.get_args(Scope))} "
                "scope are supported."
            )

        if not self.has_valid_provider_type(provider):
            raise InvalidProviderType(
                "Invalid provider type. Only callable providers are allowed."
            )

        if self.mode == "sync" and (
            inspect.isasyncgenfunction(provider)
            or inspect.iscoroutinefunction(provider)
        ):
            raise InvalidMode(
                f"Cannot bind asynchronous provider "
                f"`{self.get_qualname(provider)}` in `sync` mode."
            )

        if self.has_binding(interface) and not override:
            raise ProviderAlreadyBound(
                f"Provider interface `{self.get_qualname(interface)}` already bound."
            )

        binding = Binding(provider=provider, scope=scope)

        self.validate_sub_providers(interface, binding)

        self.bindings[interface] = binding

    def provide(
        self, *, scope: t.Optional[Scope] = None, override: bool = False
    ) -> t.Callable[[Provider], t.Any]:
        def provider_func(provider: Provider) -> t.Any:
            interface = self.get_provider_annotation(provider)
            self.bind(interface, provider, scope=scope, override=override)

        return provider_func

    @staticmethod
    def has_valid_scope(scope: Scope) -> bool:
        return scope in t.get_args(Scope)

    @staticmethod
    def has_valid_provider_type(provider: Provider) -> bool:
        return callable(provider)

    def validate_sub_providers(
        self, interface: t.Type[InterfaceT], binding: Binding
    ) -> None:
        related_bindings = []

        provider, scope = binding.provider, binding.scope

        for parameter in self.get_signature(provider).parameters.values():
            if parameter.annotation is inspect._empty:  # noqa
                raise MissingProviderAnnotation(
                    f"Missing provider `{self.get_qualname(provider)}` "
                    f"dependency `{parameter.name}` annotation."
                )
            try:
                sub_binding = self.get_binding(parameter.annotation)
                related_bindings.append((sub_binding, True))
            except LookupError:
                self.lazy_bindings[parameter.annotation].append(
                    LazyBinding(
                        interface=interface,
                        parameter_name=parameter.name,
                        binding=binding,
                    )
                )

        for lazy_binding in self.lazy_bindings.pop(interface, []):
            try:
                sub_binding = self.get_binding(lazy_binding.interface)
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
                    f"{self.get_qualname(related_binding.provider)}`."
                )

    def validate_bindings(self) -> None:
        if self.lazy_bindings:
            messages = []
            for lazy_interface, sub_bindings in self.lazy_bindings.items():
                for sub_binding in sub_bindings:
                    provider = sub_binding.binding.provider
                    parameter_name = sub_binding.parameter_name
                    provider_name = self.get_qualname(provider)
                    messages.append(
                        f"- `{provider_name}` has unknown `{parameter_name}`:"
                        f" `{self.get_qualname(lazy_interface)}` parameter"
                    )
            message = "\n".join(messages)
            raise UnknownProviderDependency(
                f"Unknown provider dependencies detected:\n{message}."
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
            if not isinstance(parameter.default, Dependency):
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
        module_name = getattr(obj, "__module__", "__main__")
        return f"{module_name}.{qualname}".removeprefix("builtins.")


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
        provider = self.get_binding(interface).provider
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
    ) -> t.Tuple[t.List[t.Any], t.Dict[str, t.Any]]:
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
