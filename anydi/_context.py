import contextlib
from types import TracebackType
from typing import Any, Callable

from typing_extensions import Self

from ._utils import run_async




class ScopedContext:
    """ScopedContext base class."""

    __slots__ = ("_instances", "_stack", "_async_stack")

    def __init__(self) -> None:
        self._instances: dict[type[Any], Any] = {}
        self._stack = contextlib.ExitStack()
        self._async_stack = contextlib.AsyncExitStack()

    def get(self, interface: type[Any]) -> Any | None:
        """Get an instance from the context."""
        return self._instances.get(interface)

    def set(self, interface: type[Any], value: Any) -> None:
        """Set an instance in the context."""
        self._instances[interface] = value

    def enter(self, cm: contextlib.AbstractContextManager[Any]) -> Any:
        """Enter the context."""
        return self._stack.enter_context(cm)

    async def aenter(self, cm: contextlib.AbstractAsyncContextManager[Any]) -> Any:
        """Enter the context asynchronously."""
        return await self._async_stack.enter_async_context(cm)

    def __setitem__(self, interface: type[Any], value: Any) -> None:
        self._instances[interface] = value

    def __getitem__(self, interface: type[Any]) -> Any:
        return self._instances[interface]

    def __contains__(self, interface: type[Any]) -> bool:
        return interface in self._instances

    def __delitem__(self, interface: type[Any]) -> None:
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
        return await run_async(
            self.__exit__, exc_type, exc_val, exc_tb
        ) or await self._async_stack.__aexit__(exc_type, exc_val, exc_tb)

    async def aclose(self) -> None:
        """Close the scoped context asynchronously."""
        await self.__aexit__(None, None, None)


class ScopedRegistry:
    def __init__(self):
        self._scope_funcs = {}
        self._contexts = {}

    def register(self, scope: str, scope_func: Callable[[], str]) -> None:
        self._scope_funcs[scope] = scope_func

    def _get_ident(self, scope: str) -> str:
        scope_func = self._scope_funcs.get(scope)
        if scope_func is None:
            raise KeyError(f"Scope {scope} is not registered.")
        return f"{scope}_{scope_func()}"

    def get_context(self, scope: str) -> ScopedContext:
        ident = self._get_ident(scope)
        if ident not in self._contexts:
            self._contexts[ident] = ScopedContext()
        return self._contexts[ident]

    def close(self, scope: str) -> None:
        ident = self._get_ident(scope)
        if ident in self._contexts:
            self._contexts[ident].close()
            del self._contexts[ident]
