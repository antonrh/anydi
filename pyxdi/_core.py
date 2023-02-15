from __future__ import annotations

import abc
import contextlib
import inspect
import typing as t
from collections import defaultdict
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from types import TracebackType

from ._contstants import DEFAULT_AUTOBIND, DEFAULT_SCOPE
from ._exceptions import (
    BindingDoesNotExist,
    InvalidMode,
    InvalidProviderType,
    InvalidScope,
    MissingAnnotation,
    NotSupportedAnnotation,
    ProviderAlreadyBound,
    ScopeMismatch,
    UnknownDependency,
)
from ._types import InterfaceT, Mode, Provider, Scope

ALLOWED_SCOPES: t.Dict[Scope, t.List[Scope]] = {
    "singleton": ["singleton"],
    "request": ["request", "singleton"],
    "transient": ["transient", "singleton", "request"],
}


class Dependency:
    __slots__ = ()


def DependencyParam() -> t.Any:  # noqa
    return Dependency()


@dataclass(frozen=True)
class Binding:
    provider: Provider
    scope: Scope


@dataclass(frozen=True)
class UnresolvedBinding:
    interface: t.Type[t.Any]
    parameter_name: str
    binding: Binding


@dataclass(frozen=True)
class UnresolvedDependency:
    parameter_name: str
    obj: t.Callable[..., t.Any]


class BaseDI(abc.ABC):
    mode: t.ClassVar[Mode]

    def __init__(
        self, default_scope: t.Optional[Scope] = None, autobind: t.Optional[bool] = None
    ) -> None:
        self.default_scope = default_scope or DEFAULT_SCOPE
        self.autobind = autobind or DEFAULT_AUTOBIND
        self.bindings: t.Dict[t.Type[t.Any], Binding] = {}
        self.signature_cache: t.Dict[t.Callable[..., t.Any], inspect.Signature] = {}
        self.unresolved_bindings: t.Dict[
            t.Type[t.Any], t.List[UnresolvedBinding]
        ] = defaultdict(list)
        self.unresolved_dependencies: t.Dict[t.Type[t.Any], UnresolvedDependency] = {}

    def get_binding(self, interface: t.Type[InterfaceT]) -> Binding:
        try:
            return self.bindings[interface]
        except KeyError:
            raise BindingDoesNotExist(
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

    def has_valid_provider_type(self, provider: Provider) -> bool:
        return (
            inspect.isfunction(provider)
            or inspect.isgeneratorfunction(provider)
            or inspect.iscoroutinefunction(provider)
            or inspect.isasyncgenfunction(provider)
            or (self.autobind and inspect.isclass(provider))
        )

    def validate_sub_providers(
        self, interface: t.Type[InterfaceT], binding: Binding
    ) -> None:
        related_bindings = []

        provider, scope = binding.provider, binding.scope

        for parameter in self.get_signature(provider).parameters.values():
            if parameter.annotation is inspect._empty:  # noqa
                raise MissingAnnotation(
                    f"Missing provider `{self.get_qualname(provider)}` "
                    f"dependency `{parameter.name}` annotation."
                )
            try:
                sub_binding = self.get_binding(parameter.annotation)
                related_bindings.append((sub_binding, True))
            except BindingDoesNotExist:
                self.unresolved_bindings[parameter.annotation].append(
                    UnresolvedBinding(
                        interface=interface,
                        parameter_name=parameter.name,
                        binding=binding,
                    )
                )

        for unresolved_binding in self.unresolved_bindings.pop(interface, []):
            sub_binding = self.get_binding(unresolved_binding.interface)  # noqa
            related_bindings.append((sub_binding, False))

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

    def validate(self) -> None:
        if self.unresolved_bindings:
            messages = []
            for unresolved_interface, sub_bindings in self.unresolved_bindings.items():
                for sub_binding in sub_bindings:
                    provider = sub_binding.binding.provider
                    parameter_name = sub_binding.parameter_name
                    provider_name = self.get_qualname(provider)
                    messages.append(
                        f"- `{provider_name}` has unknown `{parameter_name}: "
                        f"{self.get_qualname(unresolved_interface)}` parameter"
                    )
            message = "\n".join(messages)
            raise UnknownDependency(
                f"Unknown provided dependencies detected:\n{message}."
            )
        if self.unresolved_dependencies:
            messages = []
            for (
                unresolved_interface,
                dependency,
            ) in self.unresolved_dependencies.items():
                parameter_name = dependency.parameter_name
                messages.append(
                    f"- `{self.get_qualname(dependency.obj)}` has unknown "
                    f"`{parameter_name}: {self.get_qualname(unresolved_interface)}` "
                    f"injected parameter"
                )
            message = "\n".join(messages)
            raise UnknownDependency(
                f"Unknown injected dependencies detected:\n{message}."
            )

    def get_provider_annotation(self, provider: Provider) -> t.Any:
        annotation = self.get_signature(provider).return_annotation

        if annotation is inspect._empty:  # noqa
            raise MissingAnnotation(
                f"Missing `{self.get_qualname(provider)}` provider return annotation."
            )

        origin = t.get_origin(annotation) or annotation
        args = t.get_args(annotation)

        # Supported generic types
        if origin in (list, dict, tuple):
            if args:
                return annotation
            else:
                raise NotSupportedAnnotation(
                    f"Cannot use `{self.get_qualname(provider)}` generic type "
                    f"annotation without actual type."
                )

        try:
            return args[0]
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
            annotation = parameter.annotation
            if annotation is inspect._empty:  # noqa
                raise MissingAnnotation(
                    f"Missing `{self.get_qualname(obj)}` parameter annotation."
                )

            if not isinstance(parameter.default, Dependency):
                continue

            if (
                not self.has_binding(annotation)
                and annotation not in self.unresolved_bindings
                and annotation not in self.unresolved_dependencies
            ):
                if self.autobind and inspect.isclass(annotation):
                    scope = getattr(annotation, "__autobind_scope__", None)
                    self.bind(annotation, annotation, scope=scope)
                else:
                    self.unresolved_dependencies[annotation] = UnresolvedDependency(
                        parameter_name=parameter.name, obj=obj
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

    def __init__(
        self, default_scope: t.Optional[Scope] = None, autobind: t.Optional[bool] = None
    ) -> None:
        super().__init__(default_scope, autobind)
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

        @wraps(obj)
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
        return provider(*args, **kwargs)

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
        if not self.di.has_binding(interface):
            self.di.bind(interface, lambda: instance, scope=self.scope)

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
