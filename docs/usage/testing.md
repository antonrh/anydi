# Testing

To use `AnyDI` with your testing framework, call the `.override(interface=..., instance=...)` context manager
to temporarily replace a dependency with an overridden instance during testing. This allows you to isolate the code being tested from its dependencies.
The `container.override()` context manager ensures that the overridden instance is used only within the context of the `with` block.
Once the block is exited, the original dependency is restored.

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

## Pytest Plugin

`AnyDI` provides a pytest plugin that automatically injects dependencies into test functions, eliminating boilerplate code and making tests cleaner.

### Configuration

#### Container Setup

There are two ways to provide a container for your tests:

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

Alternatively, override a `container` fixture in your test suite (e.g., in `conftest.py`):

```python
import pytest

from anydi import Container

from myapp import container as myapp_container


@pytest.fixture(scope="session")
def container() -> Container:
    return myapp_container
```

**Note:** The fixture approach takes priority over the configuration if both are defined.

### Auto-Injection Mode

By default, you need to mark tests with `@pytest.mark.inject` to enable dependency injection. To automatically inject dependencies into all test functions, set `anydi_autoinject` to `True`:

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

#### Basic Injection

Use the `@pytest.mark.inject` decorator to inject dependencies into specific test functions:

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

Dependencies are automatically resolved from the container based on type annotations.

#### Fixture Priority

Pytest fixtures always take priority over dependency injection. If a pytest fixture and the `@pytest.mark.inject` decorator both provide a value for the same parameter name, the fixture value will be used.

#### Fixture Injection

`anydi_fixture_inject_enabled` toggles dependency injection for fixtures annotated with `@pytest.mark.inject`. It is **disabled** by default, so you need to opt in explicitly if you want fixtures to benefit from container injection. This option performs heavy monkey patching of `pytest.fixture` and is considered experimental, so enable it only if you understand the trade-offs:

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

With fixture injection enabled, use the marker on any fixture and annotate the parameters you want resolved from the container. This works for synchronous, generator, and async fixtures (async fixtures still require the `anyio` plugin, just like async tests):

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
