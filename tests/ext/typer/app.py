from typing import Annotated

import typer

from anydi import Container, Inject, Provide
from anydi.ext.typer import install

container = Container()


@container.provider(scope="singleton")
def greeting() -> str:
    return "Hello"


@container.provider(scope="singleton")
def name() -> Annotated[str, "name"]:
    return "World"


@container.provider(scope="singleton")
def count() -> Annotated[int, "count"]:
    return 42


app = typer.Typer()


@app.command()
def hello(greeting_msg: str = Inject()) -> None:
    """Simple command with dependency injection."""
    typer.echo(f"{greeting_msg}, stranger!")


@app.command()
def greet(
    greeting_msg: str = Inject(),
    name_value: Annotated[str, "name"] = Inject(),
) -> None:
    """Command with multiple injected dependencies."""
    typer.echo(f"{greeting_msg}, {name_value}!")


@app.command()
def greet_with_provide(
    greeting_msg: Provide[str],
    name_value: Provide[Annotated[str, "name"]],
) -> None:
    """Command using Provide[] syntax."""
    typer.echo(f"{greeting_msg}, {name_value}!")


@app.command()
def mixed(
    greeting_msg: str = Inject(),
    user_name: str = typer.Argument(...),
    excited: bool = typer.Option(False, "--excited", "-e"),
) -> None:
    """Command with mixed injected and CLI parameters."""
    message = f"{greeting_msg}, {user_name}"
    if excited:
        message += "!"
    typer.echo(message)


@app.command()
def show_count(count_value: Annotated[int, "count"] = Inject()) -> None:
    """Command that injects a non-string type."""
    typer.echo(f"The count is: {count_value}")


# Create a sub-app for testing nested groups
sub_app = typer.Typer()


@sub_app.command()
def sub_hello(greeting_msg: str = Inject()) -> None:
    """Command in a nested group."""
    typer.echo(f"Sub: {greeting_msg}")


app.add_typer(sub_app, name="sub")


# Async commands
@app.command()
async def async_hello(greeting_msg: str = Inject()) -> None:
    """Simple async command with dependency injection."""
    typer.echo(f"{greeting_msg}, async stranger!")


@app.command()
async def async_greet(
    greeting_msg: str = Inject(),
    name_value: Annotated[str, "name"] = Inject(),
) -> None:
    """Async command with multiple injected dependencies."""
    typer.echo(f"{greeting_msg}, async {name_value}!")


@app.command()
async def async_greet_with_provide(
    greeting_msg: Provide[str],
    name_value: Provide[Annotated[str, "name"]],
) -> None:
    """Async command using Provide[] syntax."""
    typer.echo(f"{greeting_msg}, async provide {name_value}!")


# Install anydi
install(app, container)
