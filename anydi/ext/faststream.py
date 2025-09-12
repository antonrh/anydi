"""AnyDI FastStream extension."""

from __future__ import annotations

from typing import Any, cast

from fast_depends.dependencies import Depends
from faststream import ContextRepo
from faststream.broker.core.usecase import BrokerUsecase

from anydi import Container
from anydi._typing import InjectMarker, get_typed_parameters


def install(broker: BrokerUsecase[Any, Any], container: Container) -> None:
    """Install AnyDI into a FastStream broker.

    This function installs the AnyDI container into a FastStream broker by attaching
    it to the broker. It also patches the broker handlers to inject the required
    dependencies using AnyDI.
    """
    broker._container = container  # type: ignore

    for handler in _get_broken_handlers(broker):
        call = handler._original_call  # noqa
        for parameter in get_typed_parameters(call):
            container.validate_injected_parameter(parameter, call=call)


def _get_broken_handlers(broker: BrokerUsecase[Any, Any]) -> list[Any]:
    if (handlers := getattr(broker, "handlers", None)) is not None:
        return [handler.calls[0][0] for handler in handlers.values()]
    # faststream > 0.5.0
    return [
        subscriber.calls[0].handler
        for subscriber in broker._subscribers.values()  # noqa
    ]


def get_container(broker: BrokerUsecase[Any, Any]) -> Container:
    return cast(Container, getattr(broker, "_container"))  # noqa


class _Inject(Depends, InjectMarker):
    """Parameter dependency class for injecting dependencies using AnyDI."""

    def __init__(self) -> None:
        super().__init__(dependency=self._dependency, use_cache=True, cast=True)
        InjectMarker.__init__(self)

    async def _dependency(self, context: ContextRepo) -> Any:
        container = get_container(context.get("broker"))
        return await container.aresolve(self.interface)


def Inject() -> Any:
    return _Inject()
