# Typer Extension

Integrating `AnyDI` with [`Typer`](https://typer.tiangolo.com/) allows you to use dependency injection in your CLI applications. This extension supports both synchronous and asynchronous commands, making it easy to build modern CLI tools with clean dependency management.

```python
import anydi.ext.typer
import typer

from anydi import Container, Provide


class GreetingService:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"


container = Container()
container.register(GreetingService)

app = typer.Typer()


@app.command()
def hello(
    name: str,
    service: Provide[GreetingService],
) -> None:
    """Greet someone."""
    greeting = service.greet(name)
    typer.echo(greeting)


# Install AnyDI support in Typer
anydi.ext.typer.install(app, container)
```

!!! note

    To detect a dependency interface, provide a valid type annotation.

    `Provide[Service]` is equivalent to `Annotated[Service, Inject()]`.

You can also use the `Inject()` marker as a default value:

```python
from anydi import Inject


@app.command()
def hello(
    name: str,
    service: GreetingService = Inject(),
) -> None:
    """Greet someone."""
    greeting = service.greet(name)
    typer.echo(greeting)
```

## Async Commands

The extension fully supports async commands. Simply define your command as an `async` function, and `AnyDI` will automatically handle the async execution using `anyio`:

```python
import anydi.ext.typer
import typer

from anydi import Container, Provide


class DatabaseService:
    async def fetch_user(self, user_id: int) -> dict:
        # Simulate async database call
        return {"id": user_id, "name": f"User {user_id}"}


container = Container()
container.register(DatabaseService)

app = typer.Typer()


@app.command()
async def get_user(
    user_id: int,
    db: Provide[DatabaseService],
) -> None:
    """Fetch user from database."""
    user = await db.fetch_user(user_id)
    typer.echo(f"User: {user['name']}")


anydi.ext.typer.install(app, container)
```

Async commands work seamlessly with dependency injection, and you can mix both sync and async commands in the same application.

## Multiple Dependencies

You can inject multiple dependencies into a single command:

```python
from typing import Annotated

import anydi.ext.typer
import typer

from anydi import Container, Provide


class ConfigService:
    def get_api_url(self) -> str:
        return "https://api.example.com"


class HttpClient:
    def __init__(self, config: ConfigService) -> None:
        self.base_url = config.get_api_url()

    async def fetch(self, endpoint: str) -> dict:
        return {"url": f"{self.base_url}/{endpoint}"}


container = Container()
container.register(ConfigService)
container.register(HttpClient)

app = typer.Typer()


@app.command()
async def api_call(
    endpoint: str,
    config: Provide[ConfigService],
    client: Provide[HttpClient],
) -> None:
    """Make an API call."""
    typer.echo(f"API URL: {config.get_api_url()}")
    result = await client.fetch(endpoint)
    typer.echo(f"Result: {result}")


anydi.ext.typer.install(app, container)
```

## Callbacks

You can use dependency injection in Typer callbacks (common options/setup):

```python
import anydi.ext.typer
import typer

from anydi import Container, Provide


class AppConfig:
    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose


container = Container()
container.register(AppConfig)

app = typer.Typer()


@app.callback()
def main_callback(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    config: Provide[AppConfig],
) -> None:
    """Main application."""
    config.verbose = verbose
    if config.verbose:
        typer.echo("Verbose mode enabled")


@app.command()
def process(
    name: str,
    config: Provide[AppConfig],
) -> None:
    """Process something."""
    if config.verbose:
        typer.echo(f"Processing: {name}")
    typer.echo("Done!")


anydi.ext.typer.install(app, container)
```

## Nested Apps

The extension automatically supports nested Typer apps (command groups):

```python
import anydi.ext.typer
import typer

from anydi import Container, Provide


class UserService:
    def create_user(self, name: str) -> str:
        return f"Created user: {name}"

    def delete_user(self, user_id: int) -> str:
        return f"Deleted user: {user_id}"


container = Container()
container.register(UserService)

# Main app
app = typer.Typer()

# Sub-app for user commands
user_app = typer.Typer()


@user_app.command()
def create(
    name: str,
    service: Provide[UserService],
) -> None:
    """Create a new user."""
    result = service.create_user(name)
    typer.echo(result)


@user_app.command()
def delete(
    user_id: int,
    service: Provide[UserService],
) -> None:
    """Delete a user."""
    result = service.delete_user(user_id)
    typer.echo(result)


# Add sub-app to main app
app.add_typer(user_app, name="user")


anydi.ext.typer.install(app, container)
```

Run commands like:
```bash
python app.py user create Alice
python app.py user delete 123
```

## Automatic Scope Context Management

The Typer extension automatically manages scope contexts for your commands. When you use dependencies with different scopes (singleton, request, or custom), the appropriate contexts are automatically started and cleaned up.

```python
from typing import Annotated
from collections.abc import Iterator

import anydi.ext.typer
import typer

from anydi import Container, Provide


class DatabaseConnection:
    def __init__(self) -> None:
        print("Database connected")

    def close(self) -> None:
        print("Database disconnected")


container = Container()
container.register_scope("batch")


# Singleton with lifecycle management
@container.provider(scope="singleton")
def db_connection() -> Iterator[DatabaseConnection]:
    conn = DatabaseConnection()
    yield conn
    conn.close()


# Request-scoped (fresh per invocation)
@container.provider(scope="request")
def request_id() -> int:
    return 1


# Custom scope
@container.provider(scope="batch")
def batch_id() -> Annotated[str, "batch"]:
    return "batch-1"


app = typer.Typer()


@app.command()
def process(
    db: Provide[DatabaseConnection],
    req: Provide[int],
    batch: Provide[Annotated[str, "batch"]],
) -> None:
    """Command with mixed scopes."""
    typer.echo(f"Request: {req}, Batch: {batch}")


anydi.ext.typer.install(app, container)
```

When you run this command:
- The singleton container context is started (database connection is created)
- The request and batch scope contexts are started
- Your command executes with all dependencies
- All contexts are properly cleaned up (database connection is closed)

## Testing

Testing Typer commands with `AnyDI` is straightforward using the `CliRunner` and container overrides:

### Basic Testing

```python
from unittest import mock

import anydi.ext.typer
import typer
from typer.testing import CliRunner

from anydi import Container, Provide


class GreetingService:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"


container = Container()
container.register(GreetingService)

app = typer.Typer()


@app.command()
def hello(
    name: str,
    service: Provide[GreetingService],
) -> None:
    """Greet someone."""
    typer.echo(service.greet(name))


anydi.ext.typer.install(app, container)


def test_hello_command() -> None:
    """Test the hello command."""
    runner = CliRunner()
    result = runner.invoke(app, ["hello", "World"])

    assert result.exit_code == 0
    assert "Hello, World!" in result.stdout
```

### Testing with Mocked Dependencies

Use `container.override()` to replace dependencies with mocks:

```python
from unittest import mock

import anydi.ext.typer
import typer
from typer.testing import CliRunner

from anydi import Container, Provide


class EmailService:
    def send_email(self, to: str, subject: str) -> bool:
        # In real implementation, sends actual email
        return True


container = Container()
container.register(EmailService)

app = typer.Typer()


@app.command()
def send(
    email: str,
    subject: str,
    service: Provide[EmailService],
) -> None:
    """Send an email."""
    if service.send_email(email, subject):
        typer.echo(f"Email sent to {email}")
    else:
        typer.echo("Failed to send email", err=True)
        raise typer.Exit(code=1)


anydi.ext.typer.install(app, container)


def test_send_email_command() -> None:
    """Test email sending with mocked service."""
    # Create a mock service
    mock_service = mock.Mock(spec=EmailService)
    mock_service.send_email.return_value = True

    runner = CliRunner()

    # Override the EmailService with mock
    with container.override(EmailService, instance=mock_service):
        result = runner.invoke(app, ["send", "user@example.com", "Test Subject"])

    assert result.exit_code == 0
    assert "Email sent to user@example.com" in result.stdout

    # Verify the mock was called with correct arguments
    mock_service.send_email.assert_called_once_with("user@example.com", "Test Subject")


def test_send_email_failure() -> None:
    """Test email sending failure."""
    # Create a mock that simulates failure
    mock_service = mock.Mock(spec=EmailService)
    mock_service.send_email.return_value = False

    runner = CliRunner()

    with container.override(EmailService, instance=mock_service):
        result = runner.invoke(app, ["send", "user@example.com", "Test Subject"])

    assert result.exit_code == 1
    assert "Failed to send email" in result.stderr
```

### Testing Async Commands

Async commands are tested the same way as sync commands - `CliRunner` handles the async execution automatically:

```python
import anydi.ext.typer
import typer
from typer.testing import CliRunner

from anydi import Container, Provide


class DatabaseService:
    async def get_user(self, user_id: int) -> dict:
        return {"id": user_id, "name": "Test User"}


container = Container()
container.register(DatabaseService)

app = typer.Typer()


@app.command()
async def get_user(
    user_id: int,
    db: Provide[DatabaseService],
) -> None:
    """Get user by ID."""
    user = await db.get_user(user_id)
    typer.echo(f"User: {user['name']}")


anydi.ext.typer.install(app, container)


def test_async_get_user() -> None:
    """Test async command."""
    runner = CliRunner()
    result = runner.invoke(app, ["get-user", "123"])

    assert result.exit_code == 0
    assert "User: Test User" in result.stdout


def test_async_get_user_with_mock() -> None:
    """Test async command with mocked database."""
    mock_db = mock.Mock(spec=DatabaseService)
    mock_db.get_user = mock.AsyncMock(return_value={"id": 999, "name": "Mock User"})

    runner = CliRunner()

    with container.override(DatabaseService, instance=mock_db):
        result = runner.invoke(app, ["get-user", "999"])

    assert result.exit_code == 0
    assert "User: Mock User" in result.stdout
    mock_db.get_user.assert_called_once_with(999)
```
