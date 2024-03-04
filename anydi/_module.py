"""AnyDI decorators module."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Tuple, Type, TypeVar, Union

from typing_extensions import Concatenate, NamedTuple, ParamSpec

from ._types import Scope

if TYPE_CHECKING:
    from ._container import Container

T = TypeVar("T")
M = TypeVar("M", bound="Module")
P = ParamSpec("P")


class ModuleMeta(type):
    """A metaclass used for the Module base class.

    This metaclass extracts provider information from the class attributes
    and stores it in the `providers` attribute.
    """

    def __new__(cls, name: str, bases: Tuple[type, ...], attrs: Dict[str, Any]) -> Any:
        """Create a new instance of the ModuleMeta class.

        This method extracts provider information from the class attributes and
        stores it in the `providers` attribute.

        Args:
            name: The name of the class.
            bases: The base classes of the class.
            attrs: The attributes of the class.

        Returns:
            The new instance of the class.
        """
        attrs["providers"] = [
            (name, getattr(value, "__provider__"))
            for name, value in attrs.items()
            if hasattr(value, "__provider__")
        ]
        return super().__new__(cls, name, bases, attrs)


class Module(metaclass=ModuleMeta):
    """A base class for defining AnyDI modules."""

    providers: List[Tuple[str, ProviderDecoratorArgs]]

    def configure(self, container: Container) -> None:
        """Configure the AnyDI container with providers and their dependencies.

        This method can be overridden in derived classes to provide the
        configuration logic.

        Args:
            container: The AnyDI container to be configured.
        """


class ModuleRegistry:
    def __init__(self, container: Container) -> None:
        self.container = container

    def register(
        self, module: Union[Module, Type[Module], Callable[[Container], None]]
    ) -> None:
        """Register a module as a callable, module type, or module instance.

        Args:
            module: The module to register.
        """
        # Callable Module
        if inspect.isfunction(module):
            module(self.container)
            return

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
    """Decorator for marking a function or method as a provider in a AnyDI module.

    Args:
        scope: The scope in which the provided instance should be managed.
        override: Whether the provider should override existing providers
            with the same interface.

    Returns:
        A decorator that marks the target function or method as a provider.
    """

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
