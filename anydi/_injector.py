from __future__ import annotations

import inspect
from collections.abc import Awaitable
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, ParamSpec, TypeVar, cast

from ._logger import logger
from ._types import is_marker
from ._utils import get_full_qualname, get_typed_parameters

if TYPE_CHECKING:
    from ._container import Container


T = TypeVar("T", bound=Any)
P = ParamSpec("P")


class Injector:
    def __init__(self, container: Container) -> None:
        self.container = container

    def inject(
        self,
        call: Callable[P, T | Awaitable[T]],
    ) -> Callable[P, T | Awaitable[T]]:
        # Check if the inner callable has already been wrapped
        if hasattr(call, "__inject_wrapper__"):
            return cast(Callable[P, T | Awaitable[T]], call.__inject_wrapper__)

        injected_params = self._get_injected_params(call)

        if inspect.iscoroutinefunction(call):

            @wraps(call)
            async def awrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                for name, annotation in injected_params.items():
                    kwargs[name] = await self.container.aresolve(annotation)
                return cast(T, await call(*args, **kwargs))

            call.__inject_wrapper__ = awrapper  # type: ignore[attr-defined]

            return awrapper

        @wraps(call)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            for name, annotation in injected_params.items():
                kwargs[name] = self.container.resolve(annotation)
            return cast(T, call(*args, **kwargs))

        call.__inject_wrapper__ = wrapper  # type: ignore[attr-defined]

        return wrapper

    def _get_injected_params(self, call: Callable[..., Any]) -> dict[str, Any]:
        """Get the injected parameters of a callable object."""
        injected_params = {}
        for parameter in get_typed_parameters(call):
            if not is_marker(parameter.default):
                continue
            try:
                self._validate_injected_parameter(call, parameter)
            except LookupError as exc:
                if not self.container.strict:
                    logger.debug(
                        f"Cannot validate the `{get_full_qualname(call)}` parameter "
                        f"`{parameter.name}` with an annotation of "
                        f"`{get_full_qualname(parameter.annotation)} due to being "
                        "in non-strict mode. It will be validated at the first call."
                    )
                else:
                    raise exc
            injected_params[parameter.name] = parameter.annotation
        return injected_params

    def _validate_injected_parameter(
        self, call: Callable[..., Any], parameter: inspect.Parameter
    ) -> None:
        """Validate an injected parameter."""
        if parameter.annotation is inspect.Parameter.empty:
            raise TypeError(
                f"Missing `{get_full_qualname(call)}` parameter "
                f"`{parameter.name}` annotation."
            )

        if not self.container.is_registered(parameter.annotation):
            raise LookupError(
                f"`{get_full_qualname(call)}` has an unknown dependency parameter "
                f"`{parameter.name}` with an annotation of "
                f"`{get_full_qualname(parameter.annotation)}`."
            )
