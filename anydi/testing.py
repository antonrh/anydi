import contextlib
import logging
from collections.abc import Iterable, Iterator, Sequence
from typing import Any

import wrapt  # type: ignore
from typing_extensions import Self, type_repr

from ._container import Container
from ._module import ModuleDef
from ._provider import Provider, ProviderDef
from ._types import NOT_SET


class TestContainer(Container):
    __test__ = False

    def __init__(
        self,
        *,
        providers: Sequence[ProviderDef] | None = None,
        modules: Iterable[ModuleDef] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(providers=providers, modules=modules, logger=logger)
        self._override_instances: dict[Any, Any] = {}

    @classmethod
    def from_container(cls, container: Container) -> Self:
        return cls(
            providers=[
                ProviderDef(
                    interface=provider.interface,
                    call=provider.call,
                    scope=provider.scope,
                )
                for provider in container.providers.values()
            ],
            logger=container.logger,
        )

    @contextlib.contextmanager
    def override(self, interface: Any, instance: Any) -> Iterator[None]:
        """
        Override the provider for the specified interface with a specific instance.
        """
        if not self.has_provider_for(interface):
            raise LookupError(
                f"The provider interface `{type_repr(interface)}` not registered."
            )
        self._override_instances[interface] = instance
        try:
            yield
        finally:
            self._override_instances.pop(interface, None)

    def _hook_override_for(self, interface: Any) -> Any:
        return self._override_instances.get(interface, NOT_SET)

    def _hook_wrap_dependency(self, annotation: Any, value: Any) -> Any:
        return InstanceProxy(value, interface=annotation)

    def _hook_post_resolve(self, provider: Provider, instance: Any) -> Any:
        """Patch the test resolver for the instance."""
        if provider.interface in self._override_instances:
            return self._override_instances[provider.interface]

        if not hasattr(instance, "__dict__"):
            return instance

        wrapped = {
            name: value.interface
            for name, value in instance.__dict__.items()
            if isinstance(value, InstanceProxy)
        }

        # If there are no wrapped dependencies, return instance as-is
        if not wrapped:
            return instance

        # Create a dynamic subclass with custom __getattribute__ for this instance
        # This avoids class-level mutation while still intercepting attribute access
        original_class = instance.__class__

        class _ResolverClass(original_class):  # type: ignore
            def __getattribute__(_self, name: str) -> Any:
                # Skip special attributes to avoid recursion
                if name in {"__class__", "__dict__"}:
                    return object.__getattribute__(_self, name)

                # Try to resolve wrapped dependencies
                if name in wrapped:
                    _interface = wrapped[name]
                    return self.resolve(_interface)

                # Fall back to the original class's attribute access
                return original_class.__getattribute__(_self, name)

        # Change only this instance's class to the dynamic subclass
        instance.__class__ = _ResolverClass

        return instance


class InstanceProxy(wrapt.ObjectProxy):  # type: ignore
    def __init__(self, wrapped: Any, *, interface: type[Any]) -> None:
        super().__init__(wrapped)  # type: ignore
        self._self_interface = interface

    @property
    def interface(self) -> type[Any]:
        return self._self_interface
