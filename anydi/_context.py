from __future__ import annotations

import abc
import contextlib
from types import TracebackType
from typing import TYPE_CHECKING, Any, TypeVar, cast

from typing_extensions import Self, final

from ._types import AnyInterface, Interface, Provider
from ._utils import run_async

if TYPE_CHECKING:
    from ._container import Container

T = TypeVar("T")


class ScopedContext(abc.ABC):
    """ScopedContext base class."""

    def __init__(self, container: Container) -> None:
        self.container = container

    @abc.abstractmethod
    def get(self, interface: Interface[T], provider: Provider) -> T:
        """Get an instance of a dependency from the scoped context.

        Args:
            interface: The interface of the dependency.
            provider: The provider for the instance.

        Returns:
            An instance of the dependency.
        """

    @abc.abstractmethod
    async def aget(self, interface: Interface[T], provider: Provider) -> T:
        """Get an async instance of a dependency from the scoped context.

        Args:
            interface: The interface of the dependency.
            provider: The provider for the instance.

        Returns:
            An async instance of the dependency.
        """

    def _create_instance(self, provider: Provider) -> Any:
        """Create an instance using the provider.

        Args:
            provider: The provider for the instance.

        Returns:
            The created instance.

        Raises:
            TypeError: If the provider's instance is a coroutine provider
                and synchronous mode is used.
        """
        if provider.is_coroutine:
            raise TypeError(
                f"The instance for the coroutine provider `{provider}` cannot be "
                "created in synchronous mode."
            )
        args, kwargs = self._get_provider_arguments(provider)
        return provider.obj(*args, **kwargs)

    async def _acreate_instance(self, provider: Provider) -> Any:
        """Create an instance asynchronously using the provider.

        Args:
            provider: The provider for the instance.

        Returns:
            The created instance.

        Raises:
            TypeError: If the provider's instance is a coroutine provider
                and asynchronous mode is used.
        """
        args, kwargs = await self._aget_provider_arguments(provider)
        if provider.is_coroutine:
            return await provider.obj(*args, **kwargs)
        return await run_async(provider.obj, *args, **kwargs)

    def _get_provider_arguments(
        self, provider: Provider
    ) -> tuple[list[Any], dict[str, Any]]:
        """Retrieve the arguments for a provider.

        Args:
            provider: The provider object.

        Returns:
            The arguments for the provider.
        """
        args, kwargs = [], {}
        for parameter in provider.parameters:
            instance = self.container.resolve(parameter.annotation)
            if parameter.kind == parameter.POSITIONAL_ONLY:
                args.append(instance)
            else:
                kwargs[parameter.name] = instance
        return args, kwargs

    async def _aget_provider_arguments(
        self, provider: Provider
    ) -> tuple[list[Any], dict[str, Any]]:
        """Asynchronously retrieve the arguments for a provider.

        Args:
            provider: The provider object.

        Returns:
            The arguments for the provider.
        """
        args, kwargs = [], {}
        for parameter in provider.parameters:
            instance = await self.container.aresolve(parameter.annotation)
            if parameter.kind == parameter.POSITIONAL_ONLY:
                args.append(instance)
            else:
                kwargs[parameter.name] = instance
        return args, kwargs


class ResourceScopedContext(ScopedContext):
    """ScopedContext with closable resources support."""

    def __init__(self, container: Container) -> None:
        """Initialize the ScopedContext."""
        super().__init__(container)
        self._instances: dict[type[Any], Any] = {}
        self._stack = contextlib.ExitStack()
        self._async_stack = contextlib.AsyncExitStack()

    def get(self, interface: Interface[T], provider: Provider) -> T:
        """Get an instance of a dependency from the scoped context.

        Args:
            interface: The interface of the dependency.
            provider: The provider for the instance.

        Returns:
            An instance of the dependency.
        """
        instance = self._instances.get(interface)
        if instance is None:
            if provider.is_generator:
                instance = self._create_resource(provider)
            elif provider.is_async_generator:
                raise TypeError(
                    f"The provider `{provider}` cannot be started in synchronous mode "
                    "because it is an asynchronous provider. Please start the provider "
                    "in asynchronous mode before using it."
                )
            else:
                instance = self._create_instance(provider)
            self._instances[interface] = instance
        return cast(T, instance)

    async def aget(self, interface: Interface[T], provider: Provider) -> T:
        """Get an async instance of a dependency from the scoped context.

        Args:
            interface: The interface of the dependency.
            provider: The provider for the instance.

        Returns:
            An async instance of the dependency.
        """
        instance = self._instances.get(interface)
        if instance is None:
            if provider.is_generator:
                instance = await run_async(self._create_resource, provider)
            elif provider.is_async_generator:
                instance = await self._acreate_resource(provider)
            else:
                instance = await self._acreate_instance(provider)
            self._instances[interface] = instance
        return cast(T, instance)

    def has(self, interface: AnyInterface) -> bool:
        """Check if the scoped context has an instance of the dependency.

        Args:
            interface: The interface of the dependency.

        Returns:
            Whether the scoped context has an instance of the dependency.
        """
        return interface in self._instances

    def _create_resource(self, provider: Provider) -> Any:
        """Create a resource using the provider.

        Args:
            provider: The provider for the resource.

        Returns:
            The created resource.
        """
        args, kwargs = self._get_provider_arguments(provider)
        cm = contextlib.contextmanager(provider.obj)(*args, **kwargs)
        return self._stack.enter_context(cm)

    async def _acreate_resource(self, provider: Provider) -> Any:
        """Create a resource asynchronously using the provider.

        Args:
            provider: The provider for the resource.

        Returns:
            The created resource.
        """
        args, kwargs = await self._aget_provider_arguments(provider)
        cm = contextlib.asynccontextmanager(provider.obj)(*args, **kwargs)
        return await self._async_stack.enter_async_context(cm)

    def delete(self, interface: AnyInterface) -> None:
        """Delete a dependency instance from the scoped context.

        Args:
             interface: The interface of the dependency.
        """
        self._instances.pop(interface, None)

    def __enter__(self) -> Self:
        """Enter the context.

        Returns:
            The scoped context.
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context.

        Args:
            exc_type: The type of the exception, if any.
            exc_val: The exception instance, if any.
            exc_tb: The traceback, if any.
        """
        self.close()
        return

    def close(self) -> None:
        """Close the scoped context."""
        self._stack.close()

    async def __aenter__(self) -> Self:
        """Enter the context asynchronously.

        Returns:
            The scoped context.
        """
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context asynchronously.

        Args:
            exc_type: The type of the exception, if any.
            exc_val: The exception instance, if any.
            exc_tb: The traceback, if any.
        """
        await self.aclose()
        return

    async def aclose(self) -> None:
        """Close the scoped context asynchronously."""
        await run_async(self._stack.close)
        await self._async_stack.aclose()


@final
class SingletonContext(ResourceScopedContext):
    """A scoped context representing the "singleton" scope."""


@final
class RequestContext(ResourceScopedContext):
    """A scoped context representing the "request" scope."""


@final
class TransientContext(ScopedContext):
    """A scoped context representing the "transient" scope."""

    def get(self, interface: Interface[T], provider: Provider) -> T:
        """Get an instance of a dependency from the transient context.

        Args:
            interface: The interface of the dependency.
            provider: The provider for the instance.

        Returns:
            An instance of the dependency.
        """
        instance = self._create_instance(provider)
        return cast(T, instance)

    async def aget(self, interface: Interface[T], provider: Provider) -> T:
        """Get an async instance of a dependency from the transient context.

        Args:
            interface: The interface of the dependency.
            provider: The provider for the instance.

        Returns:
            An instance of the dependency.
        """
        instance = await self._acreate_instance(provider)
        return cast(T, instance)
