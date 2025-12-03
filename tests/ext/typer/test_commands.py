import typer
from typer.testing import CliRunner

from anydi import Container


def test_hello_command(app: typer.Typer, runner: CliRunner) -> None:
    """Test simple command with dependency injection."""
    result = runner.invoke(app, ["hello"])

    assert result.exit_code == 0
    assert "Hello, stranger!" in result.stdout


def test_greet_command(app: typer.Typer, runner: CliRunner) -> None:
    """Test command with multiple injected dependencies."""
    result = runner.invoke(app, ["greet"])

    assert result.exit_code == 0
    assert "Hello, World!" in result.stdout


def test_greet_with_provide(app: typer.Typer, runner: CliRunner) -> None:
    """Test command using Provide[] syntax."""
    result = runner.invoke(app, ["greet-with-provide"])

    assert result.exit_code == 0
    assert "Hello, World!" in result.stdout


def test_mixed_command(app: typer.Typer, runner: CliRunner) -> None:
    """Test command with mixed injected and CLI parameters."""
    result = runner.invoke(app, ["mixed", "Alice"])

    assert result.exit_code == 0
    assert "Hello, Alice" in result.stdout


def test_mixed_command_with_option(app: typer.Typer, runner: CliRunner) -> None:
    """Test command with mixed parameters and options."""
    result = runner.invoke(app, ["mixed", "Alice", "--excited"])

    assert result.exit_code == 0
    assert "Hello, Alice!" in result.stdout


def test_show_count_command(app: typer.Typer, runner: CliRunner) -> None:
    """Test command that injects a non-string type."""
    result = runner.invoke(app, ["show-count"])

    assert result.exit_code == 0
    assert "The count is: 42" in result.stdout


def test_sub_command(app: typer.Typer, runner: CliRunner) -> None:
    """Test command in a nested group."""
    result = runner.invoke(app, ["sub", "sub-hello"])

    assert result.exit_code == 0
    assert "Sub: Hello" in result.stdout


def test_with_container_override(
    app: typer.Typer, container: Container, runner: CliRunner
) -> None:
    """Test command with container override."""
    with container.override(str, instance="Hola"):
        result = runner.invoke(app, ["hello"])

    assert result.exit_code == 0
    assert "Hola, stranger!" in result.stdout


def test_with_mock_dependency(
    app: typer.Typer, container: Container, runner: CliRunner
) -> None:
    """Test command with mocked dependency."""
    mock_greeting = "Bonjour"

    with container.override(str, instance=mock_greeting):
        result = runner.invoke(app, ["greet"])

    assert result.exit_code == 0
    assert "Bonjour, World!" in result.stdout
