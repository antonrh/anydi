import contextlib
import inspect
import logging
from collections.abc import Iterable, Iterator, Sequence
from typing import Any, TypeVar

import wrapt  # type: ignore
from typing_extensions import Self

from ._container import Container
from ._context import InstanceContext
from ._module import ModuleDef
from ._provider import Provider, ProviderDef
from ._scope import Scope
from ._typing import type_repr

T = TypeVar("T")


class TestContainer(Container):
    __test__ = False

    def __init__(
        self,
        *,
        providers: Sequence[ProviderDef] | None = None,
        modules: Iterable[ModuleDef] | None = None,
        default_scope: Scope = "transient",
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

    def _resolve_or_create(
        self, interface: Any, create: bool, /, **defaults: Any
    ) -> Any:
        """Internal method to handle instance resolution and creation."""
        instance = super()._resolve_or_create(interface, create, **defaults)
        return self._patch_resolver(interface, instance)

    async def _aresolve_or_create(
        self, interface: Any, create: bool, /, **defaults: Any
    ) -> Any:
        """Internal method to handle instance resolution and creation asynchronously."""
        instance = await super()._aresolve_or_create(interface, create, **defaults)
        return self._patch_resolver(interface, instance)

    def _get_provider_instance(
        self,
        provider: Provider,
        parameter: inspect.Parameter,
        context: InstanceContext | None,
        /,
        **defaults: Any,
    ) -> Any:
        """Retrieve an instance of a dependency from the scoped context."""
        instance = super()._get_provider_instance(
            provider, parameter, context, **defaults
        )
        return InstanceProxy(instance, interface=parameter.annotation)

    async def _aget_provider_instance(
        self,
        provider: Provider,
        parameter: inspect.Parameter,
        context: InstanceContext | None,
        /,
        **defaults: Any,
    ) -> Any:
        """Asynchronously retrieve an instance of a dependency from the context."""
        instance = await super()._aget_provider_instance(
            provider, parameter, context, **defaults
        )
        return InstanceProxy(instance, interface=parameter.annotation)

    def _patch_resolver(self, interface: Any, instance: Any) -> Any:
        """Patch the test resolver for the instance."""
        if interface in self._override_instances:
            return self._override_instances[interface]

        if not hasattr(instance, "__dict__") or hasattr(
            instance, "__resolver_getter__"
        ):
            return instance

        wrapped = {
            name: value.interface
            for name, value in instance.__dict__.items()
            if isinstance(value, InstanceProxy)
        }

        def __resolver_getter__(name: str) -> Any:
            if name in wrapped:
                _interface = wrapped[name]
                # Resolve the dependency if it's wrapped
                return self.resolve(_interface)
            raise LookupError

        # Attach the resolver getter to the instance
        instance.__resolver_getter__ = __resolver_getter__

        if not hasattr(instance.__class__, "__getattribute_patched__"):

            def __getattribute__(_self: Any, name: str) -> Any:
                # Skip the resolver getter
                if name in {"__resolver_getter__", "__class__"}:
                    return object.__getattribute__(_self, name)

                if hasattr(_self, "__resolver_getter__"):
                    try:
                        return _self.__resolver_getter__(name)
                    except LookupError:
                        pass

                # Fall back to default behavior
                return object.__getattribute__(_self, name)

            # Apply the patched resolver if wrapped attributes exist
            instance.__class__.__getattribute__ = __getattribute__
            instance.__class__.__getattribute_patched__ = True

        return instance


class InstanceProxy(wrapt.ObjectProxy):  # type: ignore
    def __init__(self, wrapped: Any, *, interface: type[Any]) -> None:
        super().__init__(wrapped)  # type: ignore
        self._self_interface = interface

    @property
    def interface(self) -> type[Any]:
        return self._self_interface
