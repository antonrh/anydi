import typing as t

import fastapi
import pytest

import initdi
from initdi.ext.fastapi import GetInstance, Inject, install  # noqa


def test_inject_param_missing_interface() -> None:
    param = GetInstance()

    with pytest.raises(TypeError) as exc_info:
        _ = param.interface

    assert str(exc_info.value) == "Interface is not set."


def test_install_without_annotation() -> None:
    di = initdi.InitDI()

    @di.provider(scope="singleton")
    def message() -> str:
        return "Hello"

    app = fastapi.FastAPI()

    @app.get("/hello")
    def say_hello(message=Inject()) -> t.Any:  # type: ignore[no-untyped-def]
        return message

    with pytest.raises(TypeError) as exc_info:
        install(app, di)

    assert str(exc_info.value) == (
        "Missing `tests.ext.fastapi.test_ext.test_install_without_annotation"
        ".<locals>.say_hello` parameter `message` annotation."
    )


def test_install_unknown_annotation() -> None:
    di = initdi.InitDI()

    app = fastapi.FastAPI()

    @app.get("/hello")
    def say_hello(message: str = Inject()) -> t.Any:
        return message

    with pytest.raises(LookupError) as exc_info:
        install(app, di)

    assert str(exc_info.value) == (
        "`tests.ext.fastapi.test_ext.test_install_unknown_annotation"
        ".<locals>.say_hello` has an unknown dependency parameter `message` "
        "with an annotation of `str`."
    )
