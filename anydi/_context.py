from __future__ import annotations

import contextlib
import threading
from collections.abc import Iterator
from contextvars import Token
from types import TracebackType
from typing import TYPE_CHECKING, Any

import anyio.to_thread
from typing_extensions import Self

from ._async_lock import AsyncRLock
from ._types import NOT_SET, is_event_type

if TYPE_CHECKING:
    from ._container import Container


class InstanceContext:
    """A context to store instances."""

    __slots__ = ("_async_lock", "_async_stack", "_items", "_lock", "_stack")

    def __init__(self) -> None:
        self._items: dict[Any, Any] = {}
        self._stack: contextlib.ExitStack | None = None
        self._async_stack: contextlib.AsyncExitStack | None = None
        self._lock: threading.RLock | None = None
        self._async_lock: AsyncRLock | None = None

    def get(self, key: Any, default: Any = NOT_SET) -> Any:
        """Get an instance from the context."""
        return self._items.get(key, default)

    def set(self, key: Any, value: Any) -> None:
        """Set an instance in the context."""
        self._items[key] = value

    def enter(self, cm: contextlib.AbstractContextManager[Any]) -> Any:
        """Enter the context."""
        if self._stack is None:
            self._stack = contextlib.ExitStack()
        return self._stack.enter_context(cm)

    async def aenter(self, cm: contextlib.AbstractAsyncContextManager[Any]) -> Any:
        """Enter the context asynchronously."""
        if self._async_stack is None:
            self._async_stack = contextlib.AsyncExitStack()
        return await self._async_stack.enter_async_context(cm)

    def __setitem__(self, key: Any, value: Any) -> None:
        self._items[key] = value

    def __getitem__(self, key: Any) -> Any:
        return self._items[key]

    def __contains__(self, key: Any) -> bool:
        return key in self._items

    def __delitem__(self, key: Any) -> None:
        self._items.pop(key, None)

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
        if self._stack is None:
            return False
        return self._stack.__exit__(exc_type, exc_val, exc_tb)

    def close(self) -> None:
        """Close the scoped context."""
        if self._stack is not None:
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
        sync_exit = False
        async_exit = False
        if self._stack is not None:
            sync_exit = await anyio.to_thread.run_sync(
                self.__exit__, exc_type, exc_val, exc_tb
            )
        if self._async_stack is not None:
            async_exit = await self._async_stack.__aexit__(exc_type, exc_val, exc_tb)
        return bool(sync_exit) or bool(async_exit)

    async def aclose(self) -> None:
        """Close the scoped context asynchronously."""
        await self.__aexit__(None, None, None)

    def lock(self) -> threading.RLock:
        """Acquire the context lock."""
        if self._lock is None:
            self._lock = threading.RLock()
        return self._lock

    def alock(self) -> AsyncRLock:
        """Acquire the context lock asynchronously."""
        if self._async_lock is None:
            self._async_lock = AsyncRLock()
        return self._async_lock


class ScopedContext:
    """A context manager entering and leaving a scoped instance context."""

    __slots__ = ("_container", "_context", "_isolated", "_scope", "_token", "_var")

    def __init__(
        self, container: Container, scope: str, *, isolated: bool = False
    ) -> None:
        self._container = container
        self._scope = scope
        self._isolated = isolated
        self._var = container._get_scoped_context_var(scope)
        self._context: InstanceContext | None = None
        self._token: Token[InstanceContext] | None = None

    def _enter(self) -> tuple[InstanceContext, bool]:
        """Return the context to use and whether this scope created it."""
        if self._token is not None:
            raise RuntimeError(f"The {self._scope} context is already entered.")
        context = self._var.get(None)
        if context is not None and not self._isolated:
            # Reuse existing context, don't create a new one
            self._context = context
            return context, False
        context = InstanceContext()
        self._token = self._var.set(context)
        self._context = context
        return context, True

    def _events(self) -> Iterator[Any]:
        """Iterate over the event resources of the scope."""
        for dependency_type in self._container._resources.get(self._scope, ()):
            if is_event_type(dependency_type):
                yield dependency_type

    def _exit(self) -> tuple[InstanceContext, Token[InstanceContext]] | None:
        """Return the context to close and its token, or None when not owned."""
        token = self._token
        context = self._context
        if token is None or context is None:
            # The context was owned by an outer scope
            return None
        self._token = None
        return context, token

    def __enter__(self) -> InstanceContext:
        context, created = self._enter()
        if created:
            try:
                for dependency_type in self._events():
                    self._container.resolve(dependency_type)
            except BaseException as exc:
                # Python skips `__exit__` when `__enter__` raises.
                self.__exit__(type(exc), exc, exc.__traceback__)
                raise
        return context

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Any:
        owned = self._exit()
        if owned is None:
            return None
        context, token = owned
        try:
            return context.__exit__(exc_type, exc_val, exc_tb)
        finally:
            self._var.reset(token)

    async def __aenter__(self) -> InstanceContext:
        context, created = self._enter()
        if created:
            try:
                for dependency_type in self._events():
                    await self._container.aresolve(dependency_type)
            except BaseException as exc:
                # Python skips `__aexit__` when `__aenter__` raises.
                await self.__aexit__(type(exc), exc, exc.__traceback__)
                raise
        return context

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Any:
        owned = self._exit()
        if owned is None:
            return None
        context, token = owned
        try:
            return await context.__aexit__(exc_type, exc_val, exc_tb)
        finally:
            self._var.reset(token)
