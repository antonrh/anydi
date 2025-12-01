"""AnyDI FastStream extension."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, cast

from fast_depends.dependencies import Dependant
from faststream import ContextRepo

from anydi import Container
from anydi._types import Inject, ProvideMarker, set_provide_factory

if TYPE_CHECKING:
    from faststream._internal.broker import BrokerUsecase

__all__ = ["install", "get_container", "Inject"]


def get_container(broker: BrokerUsecase[Any, Any]) -> Container:
    """Get the AnyDI container from a FastStream broker."""
    return cast(Container, getattr(broker, "_container"))  # noqa


class _ProvideMarker(Dependant, ProvideMarker):
    def __init__(self) -> None:
        super().__init__(self._dependency, use_cache=True, cast=True, cast_result=True)
        ProvideMarker.__init__(self)

    async def _dependency(self, context: ContextRepo) -> Any:
        container = get_container(context.get("broker"))
        return await container.aresolve(self.interface)


# Configure Inject() and Provide[T] to use FastStream-specific marker
set_provide_factory(_ProvideMarker)


def _get_broker_handlers(broker: BrokerUsecase[Any, Any]) -> list[Any]:
    return [subscriber.calls[0].handler for subscriber in broker.subscribers]


def install(broker: BrokerUsecase[Any, Any], container: Container) -> None:
    """Install AnyDI into a FastStream broker."""
    broker._container = container  # type: ignore
    for handler in _get_broker_handlers(broker):
        call = handler._original_call  # noqa
        for parameter in inspect.signature(call, eval_str=True).parameters.values():
            container.validate_injected_parameter(parameter, call=call)
