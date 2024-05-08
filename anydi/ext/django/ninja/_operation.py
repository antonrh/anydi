from __future__ import annotations

from typing import Any

from django.http import HttpRequest, HttpResponseBase
from ninja.operation import (
    AsyncOperation as BaseAsyncOperation,  # noqa
    Operation as BaseOperation,
)

from anydi.ext.django import container

from ._signature import ViewSignature


def _update_exc_args(exc: Exception) -> None:
    if isinstance(exc, TypeError) and "required positional argument" in str(exc):
        msg = "Did you fail to use functools.wraps() in a decorator?"
        msg = f"{exc.args[0]}: {msg}" if exc.args else msg
        exc.args = (msg,) + exc.args[1:]


class Operation(BaseOperation):
    signature: ViewSignature

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.dependencies = self.signature.dependencies

    def run(self, request: HttpRequest, **kw: Any) -> HttpResponseBase:
        error = self._run_checks(request)
        if error:
            return error
        try:
            temporal_response = self.api.create_temporal_response(request)
            values = self._get_values(request, kw, temporal_response)
            values.update(self._get_dependencies())
            result = self.view_func(request, **values)
            return self._result_to_response(request, result, temporal_response)
        except Exception as e:
            _update_exc_args(e)
            return self.api.on_exception(request, e)

    def _get_dependencies(self) -> dict[str, Any]:
        return {
            name: container.resolve(interface) for name, interface in self.dependencies
        }


class AsyncOperation(BaseAsyncOperation):
    signature: ViewSignature

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.dependencies = self.signature.dependencies

    async def run(self, request: HttpRequest, **kw: Any) -> HttpResponseBase:  # type: ignore
        error = await self._run_checks(request)
        if error:
            return error
        try:
            temporal_response = self.api.create_temporal_response(request)
            values = self._get_values(request, kw, temporal_response)
            values.update(await self._get_dependencies())
            result = await self.view_func(request, **values)
            return self._result_to_response(request, result, temporal_response)
        except Exception as e:
            _update_exc_args(e)
            return self.api.on_exception(request, e)

    async def _get_dependencies(self) -> dict[str, Any]:
        return {
            name: await container.aresolve(interface)
            for name, interface in self.dependencies
        }
