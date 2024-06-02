"""AnyDI FastStream extension."""

from __future__ import annotations

import logging
from typing import Any, cast

from fast_depends.dependencies import Depends
from faststream import ContextRepo
from faststream.broker.core.usecase import BrokerUsecase

from anydi import Container
from anydi._utils import get_typed_parameters

from ._utils import HasInterface, patch_call_parameter

logger = logging.getLogger(__name__)


def install(broker: BrokerUsecase[Any, Any], container: Container) -> None:
    """Install AnyDI into a FastStream broker.

    Args:
        broker: The broker.
        container: The container.

    This function installs the AnyDI container into a FastStream broker by attaching
    it to the broker. It also patches the broker handlers to inject the required
    dependencies using AnyDI.
    """
    broker._container = container  # type: ignore[attr-defined]

    for handler in _get_broken_handlers(broker):
        call = handler._original_call  # noqa
        for parameter in get_typed_parameters(call):
            patch_call_parameter(call, parameter, container)


def _get_broken_handlers(broker: BrokerUsecase[Any, Any]) -> list[Any]:
    if hasattr(broker, "handlers"):
        return [handler.calls[0][0] for handler in broker.handlers.values()]
    # faststream > 0.5.0
    return [
        subscriber.calls[0].handler
        for subscriber in broker._subscribers.values()  # noqa
    ]


def get_container(broker: BrokerUsecase[Any, Any]) -> Container:
    return cast(Container, getattr(broker, "_container"))  # noqa


class Resolver(HasInterface, Depends):
    """Parameter dependency class for injecting dependencies using AnyDI."""

    def __init__(self) -> None:
        super().__init__(dependency=self._dependency, use_cache=True, cast=True)

    async def _dependency(self, context: ContextRepo) -> Any:
        container = get_container(context.get("broker"))
        return await container.aresolve(self.interface)


def Inject() -> Any:  # noqa
    return Resolver()
