from __future__ import annotations

import contextlib
import threading
from types import TracebackType
from typing import Any

from typing_extensions import Self

from ._async import AsyncRLock, run_sync


class InstanceContext:
    """A context to store instances."""

    __slots__ = ("_instances", "_stack", "_async_stack", "_lock", "_async_lock")

    def __init__(self) -> None:
        self._instances: dict[Any, Any] = {}
        self._stack = contextlib.ExitStack()
        self._async_stack = contextlib.AsyncExitStack()
        self._lock = threading.RLock()
        self._async_lock = AsyncRLock()

    def get(self, interface: Any) -> Any | None:
        """Get an instance from the context."""
        return self._instances.get(interface)

    def set(self, interface: Any, value: Any) -> None:
        """Set an instance in the context."""
        self._instances[interface] = value

    def enter(self, cm: contextlib.AbstractContextManager[Any]) -> Any:
        """Enter the context."""
        return self._stack.enter_context(cm)

    async def aenter(self, cm: contextlib.AbstractAsyncContextManager[Any]) -> Any:
        """Enter the context asynchronously."""
        return await self._async_stack.enter_async_context(cm)

    def __setitem__(self, interface: Any, value: Any) -> None:
        self._instances[interface] = value

    def __getitem__(self, interface: Any) -> Any:
        return self._instances[interface]

    def __contains__(self, interface: Any) -> bool:
        return interface in self._instances

    def __delitem__(self, interface: Any) -> None:
        self._instances.pop(interface, None)

    def __enter__(self) -> Self:
        """Enter the context."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Any:
        """Exit the context."""
        return self._stack.__exit__(exc_type, exc_val, exc_tb)

    def close(self) -> None:
        """Close the scoped context."""
        self._stack.__exit__(None, None, None)

    async def __aenter__(self) -> Self:
        """Enter the context asynchronously."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """Exit the context asynchronously."""
        sync_exit = await run_sync(self.__exit__, exc_type, exc_val, exc_tb)
        async_exit = await self._async_stack.__aexit__(exc_type, exc_val, exc_tb)
        return bool(sync_exit) or bool(async_exit)

    async def aclose(self) -> None:
        """Close the scoped context asynchronously."""
        await self.__aexit__(None, None, None)

    def lock(self) -> threading.RLock:
        """Acquire the context lock."""
        return self._lock

    def alock(self) -> AsyncRLock:
        """Acquire the context lock asynchronously."""
        return self._async_lock
