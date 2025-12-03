import typer
from typer.testing import CliRunner

from anydi import Container


def test_async_hello_command(app: typer.Typer, runner: CliRunner) -> None:
    """Test simple async command with dependency injection."""
    result = runner.invoke(app, ["async-hello"])

    assert result.exit_code == 0
    assert "Hello, async stranger!" in result.stdout


def test_async_greet_command(app: typer.Typer, runner: CliRunner) -> None:
    """Test async command with multiple injected dependencies."""
    result = runner.invoke(app, ["async-greet"])

    assert result.exit_code == 0
    assert "Hello, async World!" in result.stdout


def test_async_greet_with_provide(app: typer.Typer, runner: CliRunner) -> None:
    """Test async command using Provide[] syntax."""
    result = runner.invoke(app, ["async-greet-with-provide"])

    assert result.exit_code == 0
    assert "Hello, async provide World!" in result.stdout


def test_async_with_container_override(
    app: typer.Typer, container: Container, runner: CliRunner
) -> None:
    """Test async command with container override."""
    with container.override(str, instance="Hola"):
        result = runner.invoke(app, ["async-hello"])

    assert result.exit_code == 0
    assert "Hola, async stranger!" in result.stdout
