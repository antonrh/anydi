from __future__ import annotations

import contextlib
from types import TracebackType
from typing import TYPE_CHECKING, Any

from typing_extensions import Self

from ._provider import Provider
from ._types import AnyInterface, is_event_type
from ._utils import run_async

if TYPE_CHECKING:
    from ._container import Container


class ScopedContext:
    """ScopedContext base class."""

    def __init__(
        self, container: Container, *, scope: str, start_events_only: bool = False
    ) -> None:
        self.scope = scope
        self.container = container
        self._start_events_only = start_events_only
        self._instances: dict[Any, Any] = {}
        self._stack = contextlib.ExitStack()
        self._async_stack = contextlib.AsyncExitStack()

    def set(self, interface: AnyInterface, instance: Any) -> None:
        """Set an instance of a dependency in the scoped context."""
        self._instances[interface] = instance

    def has(self, interface: AnyInterface) -> bool:
        """Check if the scoped context has an instance of the dependency."""
        return interface in self._instances

    def delete(self, interface: AnyInterface) -> None:
        """Delete a dependency instance from the scoped context."""
        self._instances.pop(interface, None)

    def get_or_create(self, provider: Provider) -> tuple[Any, bool]:
        """Get an instance of a dependency from the scoped context."""
        instance = self._instances.get(provider.interface)
        if instance is None:
            instance = self.container._create_instance(
                provider, instances=self._instances, stack=self._stack
            )
            self._instances[provider.interface] = instance
            return instance, True
        return instance, False

    async def aget_or_create(self, provider: Provider) -> tuple[Any, bool]:
        """Get an async instance of a dependency from the scoped context."""
        instance = self._instances.get(provider.interface)
        if instance is None:
            instance = await self.container._acreate_instance(
                provider,
                instances=self._instances,
                stack=self._stack,
                async_stack=self._async_stack,
            )
            self._instances[provider.interface] = instance
            return instance, True
        return instance, False

    def __enter__(self) -> Self:
        """Enter the context."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """Exit the context."""
        return self._stack.__exit__(exc_type, exc_val, exc_tb)  # type: ignore[return-value]

    def start(self) -> None:
        """Start the scoped context."""
        for interface in self.container._resource_cache.get(self.scope, []):  # noqa
            if self._start_events_only and not is_event_type(interface):
                continue
            self.container.resolve(interface)

    def close(self) -> None:
        """Close the scoped context."""
        self._stack.__exit__(None, None, None)

    async def __aenter__(self) -> Self:
        """Enter the context asynchronously."""
        await self.astart()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """Exit the context asynchronously."""
        return await run_async(
            self.__exit__, exc_type, exc_val, exc_tb
        ) or await self._async_stack.__aexit__(exc_type, exc_val, exc_tb)

    async def astart(self) -> None:
        """Start the scoped context asynchronously."""
        for interface in self.container._resource_cache.get(self.scope, []):  # noqa
            if self._start_events_only and not is_event_type(interface):
                continue
            await self.container.aresolve(interface)

    async def aclose(self) -> None:
        """Close the scoped context asynchronously."""
        await self.__aexit__(None, None, None)
