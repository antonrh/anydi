from typing import Any

import pytest
import typer

from anydi import Container, Inject
from anydi.ext.typer import install


def test_inject_param_missing_interface() -> None:
    param = Inject()

    with pytest.raises(TypeError, match="Interface is not set."):
        _ = param.interface


def test_install_without_annotation() -> None:
    container = Container()

    @container.provider(scope="singleton")
    def message() -> str:
        return "Hello"

    app = typer.Typer()

    @app.command()
    def say_hello(message=Inject()) -> Any:  # type: ignore[no-untyped-def]
        typer.echo(message)

    with pytest.raises(
        TypeError, match="Missing `(.*?).say_hello` parameter `message` annotation."
    ):
        install(app, container)


def test_install_unknown_annotation() -> None:
    container = Container()

    app = typer.Typer()

    @app.command()
    def say_hello(message: str = Inject()) -> Any:
        typer.echo(message)

    with pytest.raises(
        LookupError,
        match=(
            "`(.*?).say_hello` has an unknown dependency parameter `message` "
            "with an annotation of `str`."
        ),
    ):
        install(app, container)
