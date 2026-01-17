# Testing

To test with `AnyDI`, use the `.override(dependency_type, instance)` context manager. This replaces a dependency temporarily during testing. It helps you isolate code from its dependencies.
The `container.override()` works only inside the `with` block. When the block ends, the original dependency comes back.

```python
from dataclasses import dataclass
from unittest import mock

from anydi import Container, Inject


@dataclass(kw_only=True)
class Item:
    name: str


class Repository:
    def __init__(self) -> None:
        self.items: list[Item] = []

    def all(self) -> list[Item]:
        return self.items


class Service:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def get_items(self) -> list[Item]:
        return self.repo.all()


container = Container()


@container.inject
def get_items(service: Service = Inject()) -> list[Item]:
    return service.get_items()


def test_handler() -> None:
    repo_mock = mock.Mock(spec=Repository)
    repo_mock.all.return_value = [Item(name="mock1"), Item(name="mock2")]

    with container.override(Repository, repo_mock):
        assert get_items() == [Item(name="mock1"), Item(name="mock2")]
```

## Testing with Modules

You can create a testing module that overrides providers from your application modules. Use `@provider(scope="...", override=True)` to replace specific providers:

```python
from anydi import Container, Module, provider


class Database:
    def __init__(self, url: str) -> None:
        self.url = url


class UserService:
    def __init__(self, db: Database) -> None:
        self.db = db


class AppModule(Module):
    @provider(scope="singleton")
    def database(self) -> Database:
        return Database(url="postgresql://prod-server/db")

    @provider(scope="singleton")
    def user_service(self, db: Database) -> UserService:
        return UserService(db=db)


class TestingModule(Module):
    @provider(scope="singleton", override=True)
    def database(self) -> Database:
        return Database(url="sqlite:///:memory:")


# Setup container with both modules
container = Container()
container.register_module(AppModule())
container.register_module(TestingModule())

# UserService will use the overridden database from TestingModule
service = container.resolve(UserService)
assert service.db.url == "sqlite:///:memory:"
```

This approach is useful when you want to:

- Replace production dependencies with test doubles (e.g., in-memory databases)
- Override multiple providers in one place
- Share testing configuration across multiple test files

## Pytest Plugin

`AnyDI` has a pytest plugin that injects dependencies into test functions automatically. This makes tests simpler and cleaner.

### Configuration

#### Container setup

You can provide a container for tests in two ways:

**Option 1: Use the `anydi_container` configuration**

Set the `anydi_container` option in your `pytest.ini` or `pyproject.toml`:

```ini
# pytest.ini
[pytest]
anydi_container = myapp.container:container
```

```toml
# pyproject.toml
[tool.pytest.ini_options]
anydi_container = "myapp.container:container"
```

The configuration accepts:
- Container instances: `myapp.container:container` or `myapp.container.container`
- Factory functions: `myapp.container:create_container`

```python
# myapp/container.py
def create_container() -> Container:
    container = Container()
    # ... register providers
    return container
```

**Option 2: Define a `container` fixture**

Or you can override a `container` fixture in your test suite (e.g., in `conftest.py`):

```python
import pytest

from anydi import Container

from myapp import container as myapp_container


@pytest.fixture(scope="session")
def container() -> Container:
    return myapp_container
```

**Note:** The fixture approach takes priority over the configuration if both are defined.

### Auto-injection mode

By default, you need to mark tests with `@pytest.mark.inject` for dependency injection. To inject dependencies into all test functions automatically, set `anydi_autoinject` to `True`:

```ini
# pytest.ini
[pytest]
anydi_autoinject = true
```

```toml
# pyproject.toml
[tool.pytest.ini_options]
anydi_autoinject = true
```

### Usage

#### Basic injection

Use the `@pytest.mark.inject` decorator to inject dependencies into test functions:

```python
import pytest

from anydi import Container


@pytest.mark.inject
def test_service_get_items(container: Container, service: Service) -> None:
    repo_mock = mock.Mock(spec=Repository)
    repo_mock.all.return_value = [Item(name="mock1"), Item(name="mock2")]

    with container.override(Repository, repo_mock):
        assert service.get_items() == [Item(name="mock1"), Item(name="mock2")]
```

Dependencies are resolved from the container automatically based on type annotations.

#### Fixture priority

Pytest fixtures always have higher priority than dependency injection. If a pytest fixture and `@pytest.mark.inject` both provide the same parameter, the fixture value is used.

#### Fixture injection

`anydi_fixture_inject_enabled` enables dependency injection for fixtures with `@pytest.mark.inject`. It is **disabled** by default. You need to enable it if you want fixtures to use container injection. This option does heavy monkey patching of `pytest.fixture` and is experimental, so use it only if you understand the risks:

```ini
# pytest.ini
[pytest]
anydi_fixture_inject_enabled = true
```

```toml
# pyproject.toml
[tool.pytest.ini_options]
anydi_fixture_inject_enabled = true
```

When fixture injection is enabled, use the marker on any fixture and annotate parameters you want from the container. This works for sync, generator, and async fixtures (async fixtures still need the `anyio` plugin, like async tests):

```python
import pytest

from anydi import Container


class UserRepository:
    def get_name(self, user_id: int) -> str:
        return "Alice" if user_id == 1 else "Unknown"


class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

    def get_user_name(self, user_id: int) -> str:
        return self.repo.get_name(user_id)


@pytest.fixture(scope="session")
def container() -> Container:
    container = Container()
    container.register(UserRepository)
    container.register(UserService)
    return container


@pytest.fixture
@pytest.mark.inject
def user_service(service: UserService) -> UserService:
    return service


def test_uses_injected_fixture(user_service: UserService) -> None:
    assert user_service.get_user_name(1) == "Alice"
```

#### Testing with `.create()`

For more control over dependency injection in tests, use the `.create()` method to instantiate classes with overridden dependencies:

```python
def test_handler(container: Container) -> None:
    repo_mock = mock.Mock(spec=Repository)
    repo_mock.all.return_value = [Item(name="mock1"), Item(name="mock2")]

    service = container.create(Service, repo=repo_mock)

    assert service.get_items() == [Item(name="mock1"), Item(name="mock2")]
```
