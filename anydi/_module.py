from __future__ import annotations

import importlib
import inspect
from typing import TYPE_CHECKING, Any, Callable

from ._decorators import ProviderMetadata, is_provider

if TYPE_CHECKING:
    from ._container import Container


class ModuleMeta(type):
    """A metaclass used for the Module base class."""

    def __new__(cls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]) -> Any:
        attrs["providers"] = [
            (name, value.__provider__)
            for name, value in attrs.items()
            if is_provider(value)
        ]
        return super().__new__(cls, name, bases, attrs)


class Module(metaclass=ModuleMeta):
    """A base class for defining AnyDI modules."""

    providers: list[tuple[str, ProviderMetadata]]

    def configure(self, container: Container) -> None:
        """Configure the AnyDI container with providers and their dependencies."""


ModuleDef = Module | type[Module] | Callable[["Container"], None] | str


class ModuleRegistrar:
    def __init__(self, container: Container) -> None:
        self._container = container

    def register(self, module: ModuleDef) -> None:
        """Register a module as a callable, module type, or module instance."""
        # Callable Module
        if inspect.isfunction(module):
            module(self._container)
            return

        # Module path
        if isinstance(module, str):
            module = self.import_module_from_string(module)

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

    @staticmethod
    def import_module_from_string(dotted_path: str) -> Any:
        """Import a module or attribute from a dotted path."""
        try:
            module_path, _, attribute_name = dotted_path.rpartition(".")
            if module_path:
                module = importlib.import_module(module_path)
                return getattr(module, attribute_name)
            else:
                return importlib.import_module(attribute_name)
        except (ImportError, AttributeError) as exc:
            raise ImportError(f"Cannot import '{dotted_path}': {exc}") from exc
