"""AnyDI decorators module."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from typing_extensions import Concatenate, NamedTuple, ParamSpec

from ._types import Scope
from ._utils import import_string

if TYPE_CHECKING:
    from ._container import Container

T = TypeVar("T")
M = TypeVar("M", bound="Module")
P = ParamSpec("P")


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


class ModuleRegistry:
    def __init__(self, container: Container) -> None:
        self.container = container

    def register(
        self, module: Module | type[Module] | Callable[[Container], None] | str
    ) -> None:
        """Register a module as a callable, module type, or module instance."""

        # Callable Module
        if inspect.isfunction(module):
            module(self.container)
            return

        # Module path
        if isinstance(module, str):
            module = import_string(module)

        # Class based Module or Module type
        if inspect.isclass(module) and issubclass(module, Module):
            module = module()

        if isinstance(module, Module):
            module.configure(self.container)
            for provider_name, decorator_args in module.providers:
                obj = getattr(module, provider_name)
                self.container.provider(
                    scope=decorator_args.scope,
                    override=decorator_args.override,
                )(obj)


class ProviderDecoratorArgs(NamedTuple):
    scope: Scope
    override: bool


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
