"""AnyDI FastStream extension."""

from __future__ import annotations

import inspect
from typing import Any, cast

from fast_depends.dependencies import Depends
from faststream import ContextRepo
from faststream.broker.core.usecase import BrokerUsecase

from anydi import Container
from anydi._types import Inject, ProvideMarker, set_provide_factory

__all__ = ["install", "get_container", "Inject"]


def get_container(broker: BrokerUsecase[Any, Any]) -> Container:
    """Get the AnyDI container from a FastStream broker."""
    return cast(Container, getattr(broker, "_container"))  # noqa


class _ProvideMarker(Depends, ProvideMarker):
    def __init__(self) -> None:
        super().__init__(dependency=self._dependency, use_cache=True, cast=True)
        ProvideMarker.__init__(self)

    async def _dependency(self, context: ContextRepo) -> Any:
        container = get_container(context.get("broker"))
        return await container.aresolve(self.interface)


# Configure Inject() and Provide[T] to use FastStream-specific marker
set_provide_factory(_ProvideMarker)


def _get_broker_handlers(broker: BrokerUsecase[Any, Any]) -> list[Any]:
    if (handlers := getattr(broker, "handlers", None)) is not None:
        return [handler.calls[0][0] for handler in handlers.values()]
    return [
        subscriber.calls[0].handler
        for subscriber in broker._subscribers.values()  # noqa
    ]


def install(broker: BrokerUsecase[Any, Any], container: Container) -> None:
    """Install AnyDI into a FastStream broker."""
    broker._container = container  # type: ignore
    for handler in _get_broker_handlers(broker):
        call = handler._original_call  # noqa
        for parameter in inspect.signature(call, eval_str=True).parameters.values():
            container.validate_injected_parameter(parameter, call=call)
