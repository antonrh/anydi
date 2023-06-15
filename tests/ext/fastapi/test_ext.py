import typing as t

import fastapi
import pytest

import pyxdi
from pyxdi.exceptions import AnnotationError, UnknownDependencyError
from pyxdi.ext.fastapi import Inject, InjectParam, install  # noqa


def test_inject_param_missing_interface() -> None:
    param = InjectParam()

    with pytest.raises(AnnotationError) as exc_info:
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

    with pytest.raises(AnnotationError) as exc_info:
        install(app, di)

    assert str(exc_info.value) == (
        "Missing `tests.ext.fastapi.test_ext.test_install_without_annotation"
        ".<locals>.say_hello` parameter `message` annotation."
    )


def test_install_unknown_annotation() -> None:
    di = pyxdi.PyxDI()

    app = fastapi.FastAPI()

    @app.get("/hello")
    def say_hello(message: str = Inject()) -> t.Any:
        return message

    with pytest.raises(UnknownDependencyError) as exc_info:
        install(app, di)

    assert str(exc_info.value) == (
        "`tests.ext.fastapi.test_ext.test_install_unknown_annotation"
        ".<locals>.say_hello` includes an unrecognized parameter `message` "
        "with a dependency annotation of `str`."
    )
