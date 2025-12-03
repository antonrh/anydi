import typer
from typer.testing import CliRunner

from anydi import Container, Provide


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


# Async Commands


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


def test_async_command_no_injection() -> None:
    """Test async command without any dependency injection."""
    container = Container()
    app = typer.Typer()

    @app.command()
    async def simple_async() -> None:
        """Async command without DI or parameters."""
        typer.echo("Async command executed!")

    import anydi.ext.typer

    anydi.ext.typer.install(app, container)

    runner = CliRunner()

    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Async command executed!" in result.stdout


# Scoped Commands


def test_request_scoped_dependency() -> None:
    """Test command with request-scoped dependency."""
    container = Container()

    # Track instantiation
    instances_created = []

    @container.provider(scope="request")
    def request_id() -> str:
        instance = f"request-{len(instances_created) + 1}"
        instances_created.append(instance)
        return instance

    app = typer.Typer()

    @app.command()
    def show_request(req_id: Provide[str]) -> None:
        """Show request ID."""
        typer.echo(f"Request ID: {req_id}")

    import anydi.ext.typer

    anydi.ext.typer.install(app, container)

    runner = CliRunner()

    # First invocation
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Request ID: request-1" in result.stdout

    # Second invocation - should create new instance
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Request ID: request-2" in result.stdout

    # Verify two instances were created
    assert len(instances_created) == 2


def test_async_request_scoped_dependency() -> None:
    """Test async command with request-scoped dependency."""
    container = Container()

    instances_created = []

    @container.provider(scope="request")
    def request_counter() -> int:
        instance = len(instances_created) + 1
        instances_created.append(instance)
        return instance

    app = typer.Typer()

    @app.command()
    async def show_counter(counter: Provide[int]) -> None:
        """Show request counter."""
        typer.echo(f"Counter: {counter}")

    import anydi.ext.typer

    anydi.ext.typer.install(app, container)

    runner = CliRunner()

    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Counter: 1" in result.stdout

    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Counter: 2" in result.stdout


def test_custom_scoped_dependency() -> None:
    """Test command with custom-scoped dependency."""
    container = Container()

    # Register custom scope
    container.register_scope("batch")

    instances_created = []

    @container.provider(scope="batch")
    def batch_id() -> str:
        instance = f"batch-{len(instances_created) + 1}"
        instances_created.append(instance)
        return instance

    app = typer.Typer()

    @app.command()
    def process(batch: Provide[str]) -> None:
        """Process batch."""
        typer.echo(f"Processing: {batch}")

    import anydi.ext.typer

    anydi.ext.typer.install(app, container)

    runner = CliRunner()

    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Processing: batch-1" in result.stdout

    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Processing: batch-2" in result.stdout


def test_async_custom_scoped_dependency() -> None:
    """Test async command with custom-scoped dependency."""
    container = Container()

    container.register_scope("task")

    task_ids = []

    @container.provider(scope="task")
    def task_id() -> str:
        instance = f"task-{len(task_ids) + 1}"
        task_ids.append(instance)
        return instance

    app = typer.Typer()

    @app.command()
    async def run_task(tid: Provide[str]) -> None:
        """Run task."""
        typer.echo(f"Task: {tid}")

    import anydi.ext.typer

    anydi.ext.typer.install(app, container)

    runner = CliRunner()

    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Task: task-1" in result.stdout


def test_singleton_dependency_auto_context() -> None:
    """Test that singleton dependencies automatically start context."""
    from collections.abc import Iterator

    container = Container()

    init_called = []
    close_called = []

    class DatabaseConnection:
        def __init__(self) -> None:
            init_called.append(True)

        def close(self) -> None:
            close_called.append(True)

    @container.provider(scope="singleton")
    def db_connection() -> Iterator[DatabaseConnection]:
        conn = DatabaseConnection()
        yield conn
        conn.close()

    app = typer.Typer()

    @app.command()
    def query(db: Provide[DatabaseConnection]) -> None:
        """Run query."""
        typer.echo("Query executed")

    import anydi.ext.typer

    anydi.ext.typer.install(app, container)

    runner = CliRunner()

    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Query executed" in result.stdout

    # Verify singleton was initialized and closed
    assert len(init_called) == 1
    assert len(close_called) == 1


def test_async_singleton_dependency_auto_context() -> None:
    """Test async singleton dependencies automatically start context."""
    from collections.abc import AsyncIterator

    container = Container()

    init_called = []
    close_called = []

    class AsyncDatabase:
        async def __aenter__(self) -> "AsyncDatabase":
            init_called.append(True)
            return self

        async def __aexit__(self, *args: object) -> None:
            close_called.append(True)

    @container.provider(scope="singleton")
    async def async_db() -> AsyncIterator[AsyncDatabase]:
        db = AsyncDatabase()
        async with db:
            yield db

    app = typer.Typer()

    @app.command()
    async def query(db: Provide[AsyncDatabase]) -> None:
        """Run async query."""
        typer.echo("Async query executed")

    import anydi.ext.typer

    anydi.ext.typer.install(app, container)

    runner = CliRunner()

    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Async query executed" in result.stdout

    # Verify singleton was initialized and closed
    assert len(init_called) == 1
    assert len(close_called) == 1


def test_mixed_scopes_auto_context() -> None:
    """Test command with multiple scopes automatically managed."""
    from typing import Annotated

    container = Container()

    container.register_scope("batch")

    singleton_created = []
    request_created = []
    batch_created = []

    @container.provider(scope="singleton")
    def config() -> Annotated[str, "config"]:
        singleton_created.append(True)
        return "config-value"

    @container.provider(scope="request")
    def request_id() -> int:
        instance = len(request_created) + 1
        request_created.append(instance)
        return instance

    @container.provider(scope="batch")
    def batch_id() -> Annotated[str, "batch"]:
        instance = f"batch-{len(batch_created) + 1}"
        batch_created.append(instance)
        return instance

    app = typer.Typer()

    @app.command()
    def process(
        cfg: Provide[Annotated[str, "config"]],
        req: Provide[int],
        batch: Provide[Annotated[str, "batch"]],
    ) -> None:
        """Process with mixed scopes."""
        typer.echo(f"Config: {cfg}, Request: {req}, Batch: {batch}")

    import anydi.ext.typer

    anydi.ext.typer.install(app, container)

    runner = CliRunner()

    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Config: config-value" in result.stdout
    assert "Request: 1" in result.stdout
    assert "Batch: batch-1" in result.stdout

    # Verify singleton created once, others per request
    assert len(singleton_created) == 1
    assert len(request_created) == 1
    assert len(batch_created) == 1

    # Second invocation
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Request: 2" in result.stdout
    assert "Batch: batch-2" in result.stdout

    # Singleton still only created once
    assert len(singleton_created) == 1
    assert len(request_created) == 2
    assert len(batch_created) == 2


def test_nested_scopes_auto_context() -> None:
    """Test command with nested custom scopes."""
    from typing import Annotated

    container = Container()

    # Register nested scopes: tenant -> request
    container.register_scope("tenant", parents=["request"])

    tenant_created = []
    request_created = []

    @container.provider(scope="request")
    def request_id() -> int:
        instance = len(request_created) + 1
        request_created.append(instance)
        return instance

    @container.provider(scope="tenant")
    def tenant_id() -> Annotated[str, "tenant"]:
        instance = f"tenant-{len(tenant_created) + 1}"
        tenant_created.append(instance)
        return instance

    app = typer.Typer()

    @app.command()
    def show(req: Provide[int], tenant: Provide[Annotated[str, "tenant"]]) -> None:
        """Show IDs."""
        typer.echo(f"Request: {req}, Tenant: {tenant}")

    import anydi.ext.typer

    anydi.ext.typer.install(app, container)

    runner = CliRunner()

    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Request: 1" in result.stdout
    assert "Tenant: tenant-1" in result.stdout

    # Verify both scopes created instances
    assert len(request_created) == 1
    assert len(tenant_created) == 1
