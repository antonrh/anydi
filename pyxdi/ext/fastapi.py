import typing as t

import fastapi
from fastapi import params
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from starlette.requests import Request

import pyxdi
from pyxdi.exceptions import AnnotationError
from pyxdi.ext.starlette.middleware import RequestScopedMiddleware
from pyxdi.utils import get_signature

__all__ = ["RequestScopedMiddleware", "install", "get_di", "Inject"]


def install(app: fastapi.FastAPI, di: pyxdi.PyxDI) -> None:
    app.state.di = di  # noqa

    patched = []

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for dependant in iter_dependencies(route.dependant):
            if dependant.cache_key in patched:
                continue
            patched.append(dependant.cache_key)
            call, *params = dependant.cache_key
            if not call:
                continue  # pragma: no cover
            for parameter in get_signature(call).parameters.values():
                if not isinstance(parameter.default, InjectParam):
                    continue
                di._validate_injected_parameter(call, parameter)  # noqa
                parameter.default.interface = parameter.annotation


def get_di(request: Request) -> pyxdi.PyxDI:
    return t.cast(pyxdi.PyxDI, request.app.state.di)


class InjectParam(params.Depends):
    def __init__(self) -> None:
        super().__init__(dependency=self._dependency, use_cache=True)
        self._interface: t.Any = None

    @property
    def interface(self) -> t.Any:
        if self._interface is None:
            raise AnnotationError("Interface is not set.")
        return self._interface

    @interface.setter
    def interface(self, val: t.Any) -> None:
        self._interface = val

    async def _dependency(self, di: pyxdi.PyxDI = fastapi.Depends(get_di)) -> t.Any:
        return await di.aget_instance(self.interface)


def Inject() -> t.Any:  # noqa
    return InjectParam()


def iter_dependencies(dependant: Dependant) -> t.Iterator[Dependant]:
    yield dependant
    if dependant.dependencies:
        for sub_dependant in dependant.dependencies:
            yield from iter_dependencies(sub_dependant)
