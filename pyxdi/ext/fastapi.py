import inspect
import typing as t

import fastapi
from fastapi import params
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from starlette.requests import Request

import pyxdi
from pyxdi.ext.starlette.middleware import RequestScopedMiddleware

__all__ = ["RequestScopedMiddleware", "install", "get_di", "Inject"]


def install(app: fastapi.FastAPI, di: pyxdi.PyxDI) -> None:
    app.state.di = di  # noqa

    patched = []

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for dependant in iter_dependencies(route.dependant):
            if dependant.cache_key not in patched:
                patched.append(dependant.cache_key)
                if not dependant.call:
                    continue  # pragma: no cover
                for param in inspect.signature(dependant.call).parameters.values():
                    if isinstance(param.default, InjectParam):
                        if param.annotation is inspect._empty:  # noqa
                            raise TypeError(
                                f"The endpoint for the `{route.methods} {route.path}` "
                                "route is missing a type annotation for the "
                                f"`{param.name}` parameter. Please add a type "
                                "annotation to the parameter to resolve this issue."
                            )

                        param.default.interface = param.annotation


def get_di(request: Request) -> pyxdi.PyxDI:
    return t.cast(pyxdi.PyxDI, request.app.state.di)


class InjectParam(params.Depends):
    def __init__(self) -> None:
        super().__init__(dependency=self._dependency, use_cache=True)
        self._interface: t.Any = None

    @property
    def interface(self) -> t.Any:
        if self._interface is None:
            raise TypeError("Interface is not set.")
        return self._interface

    @interface.setter
    def interface(self, val: t.Any) -> None:
        self._interface = val

    def _dependency(self, di: pyxdi.PyxDI = fastapi.Depends(get_di)) -> t.Any:
        return di.get(self.interface)


def Inject() -> t.Any:  # noqa
    return InjectParam()


def iter_dependencies(dependant: Dependant) -> t.Iterator[Dependant]:
    yield dependant
    if dependant.dependencies:
        for sub_dependant in dependant.dependencies:
            yield from iter_dependencies(sub_dependant)
