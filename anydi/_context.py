from __future__ import annotations

import abc
import contextlib
import inspect
from types import TracebackType
from typing import TYPE_CHECKING, Any, Callable, ClassVar

from typing_extensions import Self, final

from ._provider import CallableKind, Provider
from ._types import AnyInterface, DependencyWrapper, Scope, is_event_type
from ._utils import get_full_qualname, run_async

if TYPE_CHECKING:
    from ._container import Container


class ScopedContext(abc.ABC):
    """ScopedContext base class."""

    scope: ClassVar[Scope]

    def __init__(self, container: Container, start_events_only: bool = False) -> None:
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
            if provider.kind == CallableKind.GENERATOR:
                instance = self._create_resource(provider)
            elif provider.kind == CallableKind.ASYNC_GENERATOR:
                raise TypeError(
                    f"The provider `{provider}` cannot be started in synchronous mode "
                    "because it is an asynchronous provider. Please start the provider "
                    "in asynchronous mode before using it."
                )
            else:
                instance = self._create_instance(provider)
            self._instances[provider.interface] = instance
            return instance, True
        return instance, False

    async def aget_or_create(self, provider: Provider) -> tuple[Any, bool]:
        """Get an async instance of a dependency from the scoped context."""
        instance = self._instances.get(provider.interface)
        if instance is None:
            if provider.kind == CallableKind.GENERATOR:
                instance = await run_async(self._create_resource, provider)
            elif provider.kind == CallableKind.ASYNC_GENERATOR:
                instance = await self._acreate_resource(provider)
            else:
                instance = await self._acreate_instance(provider)
            self._instances[provider.interface] = instance
            return instance, True
        return instance, False

    def _create_instance(self, provider: Provider) -> Any:
        """Create an instance using the provider."""
        if provider.kind == CallableKind.COROUTINE:
            raise TypeError(
                f"The instance for the coroutine provider `{provider}` cannot be "
                "created in synchronous mode."
            )
        args, kwargs = self._get_provided_args(provider)

        instance = provider.call(*args, **kwargs)
        if isinstance(instance, contextlib.AbstractContextManager):
            self._stack.enter_context(instance)
        return instance

    def _create_resource(self, provider: Provider) -> Any:
        """Create a resource using the provider."""
        args, kwargs = self._get_provided_args(provider)
        cm = contextlib.contextmanager(provider.call)(*args, **kwargs)
        return self._stack.enter_context(cm)

    async def _acreate_instance(self, provider: Provider) -> Any:
        """Create an instance asynchronously using the provider."""
        args, kwargs = await self._aget_provided_args(provider)
        if provider.kind == CallableKind.COROUTINE:
            return await provider.call(*args, **kwargs)
        instance = await run_async(provider.call, *args, **kwargs)
        if isinstance(instance, contextlib.AbstractAsyncContextManager):
            await self._async_stack.enter_async_context(instance)
        return instance

    async def _acreate_resource(self, provider: Provider) -> Any:
        """Create a resource asynchronously using the provider."""
        args, kwargs = await self._aget_provided_args(provider)
        cm = contextlib.asynccontextmanager(provider.call)(*args, **kwargs)
        return await self._async_stack.enter_async_context(cm)

    def _resolve_parameter(
        self, provider: Provider, parameter: inspect.Parameter
    ) -> Any:
        self._validate_resolvable_parameter(parameter, call=provider.call)
        return self.container.resolve(parameter.annotation)

    async def _aresolve_parameter(
        self, provider: Provider, parameter: inspect.Parameter
    ) -> Any:
        self._validate_resolvable_parameter(parameter, call=provider.call)
        return await self.container.aresolve(parameter.annotation)

    def _validate_resolvable_parameter(
        self, parameter: inspect.Parameter, call: Callable[..., Any]
    ) -> None:
        """Ensure that the specified interface is resolved."""
        if parameter.annotation in self.container._unresolved_interfaces:  # noqa
            raise LookupError(
                f"You are attempting to get the parameter `{parameter.name}` with the "
                f"annotation `{get_full_qualname(parameter.annotation)}` as a "
                f"dependency into `{get_full_qualname(call)}` which is not registered "
                "or set in the scoped context."
            )

    def _get_provided_args(
        self, provider: Provider
    ) -> tuple[list[Any], dict[str, Any]]:
        """Retrieve the arguments for a provider."""
        args: list[Any] = []
        kwargs: dict[str, Any] = {}

        for parameter in provider.parameters:
            if parameter.annotation in self.container._override_instances:  # noqa
                instance = self.container._override_instances[parameter.annotation]  # noqa
            elif parameter.annotation in self._instances:
                instance = self._instances[parameter.annotation]
            else:
                try:
                    instance = self._resolve_parameter(provider, parameter)
                except LookupError:
                    if parameter.default is inspect.Parameter.empty:
                        raise
                    instance = parameter.default
                else:
                    if self.container.testing:
                        instance = DependencyWrapper(
                            interface=parameter.annotation, instance=instance
                        )
            if parameter.kind == parameter.POSITIONAL_ONLY:
                args.append(instance)
            else:
                kwargs[parameter.name] = instance
        return args, kwargs

    async def _aget_provided_args(
        self, provider: Provider
    ) -> tuple[list[Any], dict[str, Any]]:
        """Asynchronously retrieve the arguments for a provider."""
        args: list[Any] = []
        kwargs: dict[str, Any] = {}

        for parameter in provider.parameters:
            if parameter.annotation in self.container._override_instances:  # noqa
                instance = self.container._override_instances[parameter.annotation]  # noqa
            elif parameter.annotation in self._instances:
                instance = self._instances[parameter.annotation]
            else:
                try:
                    instance = await self._aresolve_parameter(provider, parameter)
                except LookupError:
                    if parameter.default is inspect.Parameter.empty:
                        raise
                    instance = parameter.default
                else:
                    if self.container.testing:
                        instance = DependencyWrapper(
                            interface=parameter.annotation, instance=instance
                        )
            if parameter.kind == parameter.POSITIONAL_ONLY:
                args.append(instance)
            else:
                kwargs[parameter.name] = instance
        return args, kwargs

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


@final
class SingletonContext(ScopedContext):
    """A scoped context representing the "singleton" scope."""

    scope = "singleton"


@final
class RequestContext(ScopedContext):
    """A scoped context representing the "request" scope."""

    scope = "request"


@final
class TransientContext(ScopedContext):
    """A scoped context representing the "transient" scope."""

    scope = "transient"

    def get_or_create(self, provider: Provider) -> tuple[Any, bool]:
        """Get or create an instance of a dependency from the transient context."""
        return self._create_instance(provider), True

    async def aget_or_create(self, provider: Provider) -> tuple[Any, bool]:
        """
        Get or create an async instance of a dependency from the transient context.
        """
        return await self._acreate_instance(provider), True
