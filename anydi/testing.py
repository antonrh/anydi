import contextlib
import logging
from collections.abc import Iterable, Iterator, Sequence
from typing import Any

import wrapt  # type: ignore
from typing_extensions import Self, type_repr

from ._container import Container
from ._module import ModuleDef
from ._provider import ProviderDef
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

    def _hook_post_resolve(self, interface: Any, instance: Any) -> Any:  # noqa: C901
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
