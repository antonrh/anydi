from typing import Any

import pytest
from fastapi import FastAPI

from anydi import Container, Inject
from anydi.ext.fastapi import install


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
