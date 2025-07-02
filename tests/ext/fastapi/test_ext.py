from typing import Any

import pytest
from fastapi import FastAPI

from anydi import Container
from anydi.ext.fastapi import Inject, install


def test_inject_param_missing_interface() -> None:
    param = Inject()

    with pytest.raises(TypeError, match="Interface is not set."):
        _ = param.interface


@pytest.mark.skip(reason="disable until strict is enforced")
def test_install_without_annotation() -> None:
    container = Container()

    @container.provider(scope="singleton")
    def message() -> str:
        return "Hello"

    app = FastAPI()

    @app.get("/hello")
    def say_hello(message=Inject()) -> Any:  # type: ignore[no-untyped-def]
        return message

    with pytest.raises(
        TypeError, match="Missing `(.*?).say_hello` parameter `message` annotation."
    ):
        install(app, container)


@pytest.mark.skip(reason="disable until strict is enforced")
def test_install_unknown_annotation() -> None:
    container = Container()

    app = FastAPI()

    @app.get("/hello")
    def say_hello(message: str = Inject()) -> Any:
        return message

    with pytest.raises(
        LookupError,
        match=(
            "`(.*?).say_hello` has an unknown dependency parameter `message` "
            "with an annotation of `str`."
        ),
    ):
        install(app, container)
