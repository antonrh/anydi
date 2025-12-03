from typing import Annotated

import typer
from typer.testing import CliRunner

from anydi import Container, Inject, Provide


def test_app_callback_with_inject() -> None:
    """Test main app callback with dependency injection using Inject()."""
    container = Container()

    @container.provider(scope="singleton")
    def config_value() -> str:
        return "Production"

    app = typer.Typer()

    # Track if callback was called
    callback_called = False
    received_config = None

    @app.callback()
    def main_callback(config: str = Inject()) -> None:
        """Main callback with injected dependency."""
        nonlocal callback_called, received_config
        callback_called = True
        received_config = config

    @app.command()
    def status() -> None:
        """Simple command."""
        typer.echo("OK")

    from anydi.ext.typer import install

    install(app, container)

    runner = CliRunner()
    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert callback_called
    assert received_config == "Production"


def test_app_callback_with_provide() -> None:
    """Test main app callback with dependency injection using Provide[]."""
    container = Container()

    @container.provider(scope="singleton")
    def app_name() -> Annotated[str, "app_name"]:
        return "MyApp"

    app = typer.Typer()

    # Track if callback was called
    callback_called = False
    received_name = None

    @app.callback()
    def main_callback(name: Provide[Annotated[str, "app_name"]]) -> None:
        """Main callback with Provide annotation."""
        nonlocal callback_called, received_name
        callback_called = True
        received_name = name

    @app.command()
    def info() -> None:
        """Simple command."""
        typer.echo("Info")

    from anydi.ext.typer import install

    install(app, container)

    runner = CliRunner()
    result = runner.invoke(app, ["info"])

    assert result.exit_code == 0
    assert callback_called
    assert received_name == "MyApp"


def test_app_callback_with_mixed_params() -> None:
    """Test main app callback with mixed injected and CLI parameters."""
    container = Container()

    @container.provider(scope="singleton")
    def default_env() -> str:
        return "development"

    app = typer.Typer()

    # Track callback parameters
    received_params = {}

    @app.callback()
    def main_callback(
        env: str = Inject(),
        verbose: bool = typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Main callback with mixed parameters."""
        received_params["env"] = env
        received_params["verbose"] = verbose

    @app.command()
    def deploy() -> None:
        """Deploy command."""
        typer.echo("Deploying")

    from anydi.ext.typer import install

    install(app, container)

    runner = CliRunner()

    # Test without verbose flag
    result = runner.invoke(app, ["deploy"])
    assert result.exit_code == 0
    assert received_params["env"] == "development"
    assert received_params["verbose"] is False

    # Test with verbose flag
    received_params.clear()
    result = runner.invoke(app, ["--verbose", "deploy"])
    assert result.exit_code == 0
    assert received_params["env"] == "development"
    assert received_params["verbose"] is True


def test_app_callback_without_injection() -> None:
    """Test that app callback without injection still works."""
    container = Container()

    @container.provider(scope="singleton")
    def greeting() -> str:
        return "Hello"

    app = typer.Typer()

    callback_called = False

    @app.callback()
    def main_callback() -> None:
        """Main callback without dependencies."""
        nonlocal callback_called
        callback_called = True

    @app.command()
    def test_cmd(greeting_msg: str = Inject()) -> None:
        """Command with injection."""
        typer.echo(greeting_msg)

    from anydi.ext.typer import install

    install(app, container)

    runner = CliRunner()
    result = runner.invoke(app, ["test-cmd"])

    assert result.exit_code == 0
    assert callback_called
    assert "Hello" in result.stdout


def test_nested_app_with_callback() -> None:
    """Test nested Typer app with its own callback."""
    container = Container()

    @container.provider(scope="singleton")
    def main_config() -> Annotated[str, "main"]:
        return "MainConfig"

    @container.provider(scope="singleton")
    def sub_config() -> Annotated[str, "sub"]:
        return "SubConfig"

    main_app = typer.Typer()
    sub_app = typer.Typer()

    # Track callbacks
    main_callback_called = False
    sub_callback_called = False
    main_received = None
    sub_received = None

    @main_app.callback()
    def main_callback(config: Annotated[str, "main"] = Inject()) -> None:
        """Main app callback."""
        nonlocal main_callback_called, main_received
        main_callback_called = True
        main_received = config

    @sub_app.callback()
    def sub_callback(config: Annotated[str, "sub"] = Inject()) -> None:
        """Sub app callback."""
        nonlocal sub_callback_called, sub_received
        sub_callback_called = True
        sub_received = config

    @sub_app.command()
    def sub_cmd() -> None:
        """Sub command."""
        typer.echo("SubCommand")

    main_app.add_typer(sub_app, name="sub")

    from anydi.ext.typer import install

    install(main_app, container)

    runner = CliRunner()
    result = runner.invoke(main_app, ["sub", "sub-cmd"])

    assert result.exit_code == 0
    assert main_callback_called
    assert sub_callback_called
    assert main_received == "MainConfig"
    assert sub_received == "SubConfig"
