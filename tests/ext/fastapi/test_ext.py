import typing as t

import fastapi
import pytest

import pyxdi
from pyxdi.ext.fastapi import Inject, InjectParam, install  # noqa


def test_inject_param_missing_interface() -> None:
    param = InjectParam()

    with pytest.raises(TypeError) as exc_info:
        _ = param.interface

    assert str(exc_info.value) == "Interface is not set."


def test_install_without_annotation() -> None:
    di = pyxdi.PyxDI()

    @di.provider
    def message() -> str:
        return "Hello"

    app = fastapi.FastAPI()

    @app.get("/hello")
    def say_hello(message=Inject()) -> t.Any:  # type: ignore[no-untyped-def]
        return message

    with pytest.raises(TypeError) as exc_info:
        install(app, di)

    assert str(exc_info.value) == (
        "The endpoint for the `{'GET'} /hello` route is missing a type annotation for "
        "the `message` parameter. Please add a type annotation to the parameter to "
        "resolve this issue."
    )
