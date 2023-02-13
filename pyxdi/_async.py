from __future__ import annotations

import contextlib
import inspect
import typing as t
from contextvars import ContextVar
from functools import partial
from types import TracebackType

import anyio

from ._core import BaseDI
from ._types import InterfaceT, Provider, Scope


class AsyncDI(BaseDI):
    mode = "async"

    def __init__(self, default_scope: t.Optional[Scope] = None) -> None:
        super().__init__(default_scope)
        self.singleton_context = AsyncContext(self, scope="singleton")
        self.request_context_var: ContextVar[t.Optional[AsyncContext]] = ContextVar(
            "request_context", default=None
        )

    async def get(self, interface: t.Type[InterfaceT]) -> InterfaceT:
        binding = self.get_binding(interface)

        if binding.scope == "singleton":
            return await self.singleton_context.get(interface)

        elif binding.scope == "request":
            request_registry = self.request_context_var.get()
            if request_registry is None:
                raise LookupError("Request context is not started.")
            return await request_registry.get(interface)

        return t.cast(InterfaceT, await self.create_instance(interface))

    async def close(self) -> None:
        await self.singleton_context.close()

    @contextlib.asynccontextmanager
    async def request_context(self) -> t.AsyncIterator[AsyncContext]:
        async with AsyncContext(di=self, scope="request") as context:
            token = self.request_context_var.set(context)
            yield context
            self.request_context_var.reset(token)

    def inject_callable(self, target: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        injectable_params = self.get_injectable_params(target)

        async def wrapped(*args: t.Any, **kwargs: t.Any) -> t.Any:
            for name, annotation in injectable_params.items():
                kwargs[name] = await self.get(annotation)
            return await target(*args, **kwargs)

        def sync_wrapped(*args: t.Any, **kwargs: t.Any) -> t.Any:
            for name, annotation in injectable_params.items():
                kwargs[name] = anyio.from_thread.run(self.get, annotation)
            return target(*args, **kwargs)

        if inspect.iscoroutinefunction(target):
            return wrapped

        return sync_wrapped

    async def create_instance(
        self,
        interface: t.Type[InterfaceT],
        stack: contextlib.AsyncExitStack | None = None,
        sync_stack: contextlib.ExitStack | None = None,
    ) -> t.Any:
        dependency = self.get_binding(interface).provider
        args, kwargs = await self.get_provider_arguments(dependency)
        if inspect.isasyncgenfunction(dependency):
            acm = contextlib.asynccontextmanager(dependency)(*args, **kwargs)
            if stack:
                return await stack.enter_async_context(acm)
            async with contextlib.AsyncExitStack() as stack:
                return await stack.enter_async_context(acm)
        if inspect.isgeneratorfunction(dependency):
            cm = contextlib.contextmanager(dependency)(*args, **kwargs)
            if sync_stack:
                return await anyio.to_thread.run_sync(sync_stack.enter_context, cm)
            sync_stack = contextlib.ExitStack()
            try:
                return await anyio.to_thread.run_sync(sync_stack.enter_context, cm)
            finally:
                return await anyio.to_thread.run_sync(sync_stack.close)
        elif inspect.iscoroutinefunction(dependency):
            return await dependency(*args, **kwargs)
        elif inspect.isfunction(dependency):
            return await anyio.to_thread.run_sync(partial(dependency, *args, **kwargs))
        return dependency

    async def get_provider_arguments(
        self, provider: Provider
    ) -> tuple[list[t.Any], dict[str, t.Any]]:
        args = []
        kwargs = {}
        signature = inspect.signature(provider)
        for parameter in signature.parameters.values():
            instance = await self.get(parameter.annotation)
            if parameter.kind == parameter.POSITIONAL_ONLY:
                args.append(instance)
            else:
                kwargs[parameter.name] = instance
        return args, kwargs


class AsyncContext:
    def __init__(self, di: AsyncDI, scope: Scope) -> None:
        self.di = di
        self.scope = scope
        self.instances: dict[t.Any, t.Any] = {}
        self.stack = contextlib.AsyncExitStack()
        self.sync_stack = contextlib.ExitStack()

    async def get(self, interface: t.Type[InterfaceT]) -> InterfaceT:
        if (instance := self.instances.get(interface)) is None:
            instance = await self.di.create_instance(
                interface, stack=self.stack, sync_stack=self.sync_stack
            )
            self.instances[interface] = instance
        return t.cast(InterfaceT, instance)

    def set(self, interface: t.Type[InterfaceT], instance: t.Any) -> None:
        self.di.bind(interface, instance, scope=self.scope)

    async def close(self) -> None:
        await self.stack.aclose()
        await anyio.to_thread.run_sync(self.sync_stack.close)

    async def __aenter__(self) -> AsyncContext:
        return self

    async def __aexit__(
        self,
        exc_type: t.Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()
