from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Callable

from ._utils import import_string

if TYPE_CHECKING:
    from ._container import Container
    from ._decorators import ProviderMetadata


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

    providers: list[tuple[str, ProviderMetadata]]

    def configure(self, container: Container) -> None:
        """Configure the AnyDI container with providers and their dependencies."""


ModuleDefinition = Module | type[Module] | Callable[["Container"], None] | str


class ModuleRegistrar:
    def __init__(self, container: Container) -> None:
        self._container = container

    def register(self, module: ModuleDefinition) -> None:
        """Register a module as a callable, module type, or module instance."""
        # Callable Module
        if inspect.isfunction(module):
            module(self._container)
            return

        # Module path
        if isinstance(module, str):
            module = import_string(module)

        # Class based Module or Module type
        if inspect.isclass(module) and issubclass(module, Module):
            module = module()

        if isinstance(module, Module):
            module.configure(self._container)
            for provider_name, metadata in module.providers:
                obj = getattr(module, provider_name)
                self._container.provider(**metadata)(obj)
        else:
            raise TypeError(
                "The module must be a callable, a module type, or a module instance."
            )
