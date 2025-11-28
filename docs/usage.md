# Usage

## Providers

Providers are the backbone of `AnyDI`. A provider is a function or a class that returns an instance of a specific type.
Once a provider is registered with `Container`, it can be used to resolve dependencies throughout the application.

### Registering Providers

To register a provider, you can use the `register` method of the `Container` instance. The method takes
three arguments: the type of the object to be provided, the provider function or class, and a scope.

```python
from anydi import Container


class EmailService:
    def send(self, to: str, subject: str) -> None:
        print(f"Sending email to {to}: {subject}")


container = Container()
container.register(EmailService, scope="singleton")

service = container.resolve(EmailService)
service.send("user@example.com", "Welcome!")
```

Alternatively, you can use the `@provider` decorator to register a provider function. The decorator takes care of registering the provider with `Container`.

```python
from anydi import Container


class NotificationService:
    def notify(self, user_id: str, message: str) -> None:
        print(f"Notifying {user_id}: {message}")


container = Container()


@container.provider(scope="singleton")
def notification_service() -> NotificationService:
    return NotificationService()


service = container.resolve(NotificationService)
service.notify("user-123", "Hello!")
```

### Annotated Providers

Sometimes, it's useful to register multiple providers for the same type. For example, you might want to register multiple database connections. This can be achieved by using the `Annotated` type hint with the string argument:

```python
from typing import Annotated

from anydi import Container


class DatabaseConnection:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

    def query(self, sql: str) -> list:
        return []


container = Container()


@container.provider(scope="singleton")
def primary_db() -> Annotated[DatabaseConnection, "primary"]:
    return DatabaseConnection(host="db-primary.local", port=5432)


@container.provider(scope="singleton")
def replica_db() -> Annotated[DatabaseConnection, "replica"]:
    return DatabaseConnection(host="db-replica.local", port=5432)


primary = container.resolve(Annotated[DatabaseConnection, "primary"])
replica = container.resolve(Annotated[DatabaseConnection, "replica"])

assert primary.host == "db-primary.local"
assert replica.host == "db-replica.local"
```

In this code example, we define two providers for different database connections. The Annotated type hint with string argument allows you to specify which provider to retrieve based on the name provided within the annotation.

### Unregistering Providers

To unregister a provider, you can use the `unregister` method of the `Container` instance. The method takes
interface of the dependency to be unregistered.

```python
from anydi import Container


class PaymentService:
    def process_payment(self, amount: float, currency: str) -> bool:
        print(f"Processing {amount} {currency}")
        return True


container = Container()


@container.provider(scope="singleton")
def payment_service() -> PaymentService:
    return PaymentService()


assert container.is_registered(PaymentService)

container.unregister(PaymentService)

assert not container.is_registered(PaymentService)
```

### Resolved Providers

To check if a registered provider has a resolved instance, you can use the `is_resolved` method of the `Container` instance.
This method takes the interface of the dependency to be checked.

```python
from anydi import Container


class CacheService:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, value: str) -> None:
        self.data[key] = value


container = Container()


@container.provider(scope="singleton")
def cache_service() -> CacheService:
    return CacheService()


# Check if an instance is resolved
assert not container.is_resolved(CacheService)

cache = container.resolve(CacheService)
cache.set("name", "Alice")

assert container.is_resolved(CacheService)

container.release(CacheService)

assert not container.is_resolved(CacheService)
```

To release a provider instance, you can use the `release` method of the `Container` instance. This method takes the interface of the dependency to be reset. Alternatively, you can reset all instances with the `reset` method.

```python
from anydi import Container


class LoggerService:
    def log(self, message: str) -> None:
        print(f"[LOG] {message}")


class MetricsService:
    def record(self, metric: str, value: float) -> None:
        print(f"[METRIC] {metric}: {value}")


container = Container()
container.register(LoggerService)
container.register(MetricsService)

container.resolve(LoggerService)
container.resolve(MetricsService)

assert container.is_resolved(LoggerService)
assert container.is_resolved(MetricsService)

container.reset()

assert not container.is_resolved(LoggerService)
assert not container.is_resolved(MetricsService)
```

!!! note

    This pattern can be used while writing unit tests to ensure that each test case has a clean dependency graph.

## Scopes

`AnyDI` supports three different scopes for providers:

* `transient`
* `singleton`
* `request`

### `transient` scope

Providers with transient scope create a new instance of the object each time it's requested. You can set the scope when registering a provider.

```python
import uuid

from anydi import Container


class RequestTracker:
    def __init__(self) -> None:
        self.request_id = str(uuid.uuid4())


container = Container()


@container.provider(scope="transient")
def request_tracker() -> RequestTracker:
    return RequestTracker()


# Each resolve creates a new instance with a different request ID
tracker1 = container.resolve(RequestTracker)
tracker2 = container.resolve(RequestTracker)

assert tracker1.request_id != tracker2.request_id
```

### `singleton` scope

Providers with singleton scope create a single instance of the object and return it every time it's requested.

```python
from anydi import Container


class Service:
    def __init__(self, name: str) -> None:
        self.name = name


container = Container()


@container.provider(scope="singleton")
def service() -> Service:
    return Service(name="demo")


assert container.resolve(Service) == container.resolve(Service)
```

### `request` scope

Providers with request scope create an instance of the object for each request. The instance is only available within the context of the request.

```python
from anydi import Container


class Request:
    def __init__(self, path: str) -> None:
        self.path = path


container = Container()


@container.provider(scope="request")
def request_provider() -> Request:
    return Request(path="/")


with container.request_context():
    assert container.resolve(Request).path == "/"

container.resolve(Request)  # this will raise LookupError
```

or using asynchronous request context:

```python
from anydi import Container

container = Container()


@container.provider(scope="request")
def request_provider() -> Request:
    return Request(path="/")


async def main() -> None:
    async with container.arequest_context():
        assert (await container.aresolve(Request).path) == "/"
```

#### `request` scoped instances

In `AnyDI`, you can create `request-scoped` instances to manage dependencies that should be instantiated per request.
This is particularly useful when handling dependencies with request-specific data that need to be isolated across different requests.

To create a request context, you use the `request_context` (or `arequest_context` for async) method on the container.
This context is then used to resolve dependencies scoped to the current request.

```python
from typing import Annotated

from anydi import Container


class UserContext:
    def __init__(self, user_id: str, tenant_id: str) -> None:
        self.user_id = user_id
        self.tenant_id = tenant_id


container = Container()


@container.provider(scope="request")
def user_context(request: Request) -> Annotated[UserContext, "current_user"]:
    return UserContext(user_id=request.param, tenant_id="tenant-1")


with container.request_context() as ctx:
    ctx.set(Request, Request(param="user-456"))

    user = container.resolve(Annotated[UserContext, "current_user"])
    assert user.user_id == "user-456"
    assert user.tenant_id == "tenant-1"
```

## Resource Providers

Resource providers are special types of providers that need to be started and stopped. `AnyDI` supports synchronous and asynchronous resource providers.

### Synchronous Resources

Here is an example of a synchronous resource provider that manages the lifecycle of a Resource object:

```python
from typing import Iterator

from anydi import Container


class Resource:
    def __init__(self, name: str) -> None:
        self.name = name

    def start(self) -> None:
        print("start resource")

    def close(self) -> None:
        print("close resource")


container = Container()


@container.provider(scope="singleton")
def resource_provider() -> t.Iterator[Resource]:
    resource = Resource(name="demo")
    resource.start()
    yield resource
    resource.close()


container.start()  # start resources

assert container.resolve(Resource).name == "demo"

container.close()  # close resources
```

In this example, the resource_provider function returns an iterator that yields a single Resource object. The `.start` method is called when the resource is created, and the `.close` method is called when the resource is released.

### Asynchronous Resources

Here is an example of an asynchronous resource provider that manages the lifecycle of an asynchronous Resource object:

```python
import asyncio
from typing import AsyncIterator

from anydi import Container


class Resource:
    def __init__(self, name: str) -> None:
        self.name = name

    async def start(self) -> None:
        print("start resource")

    async def close(self) -> None:
        print("close resource")


container = Container()


@container.provider(scope="singleton")
async def resource_provider() -> AsyncIterator[Resource]:
    resource = Resource(name="demo")
    await resource.start()
    yield resource
    await resource.close()


async def main() -> None:
    await container.astart()  # start resources

    assert (await container.aresolve(Resource)).name == "demo"

    await container.aclose()  # close resources


asyncio.run(main())
```

In this example, the `resource_provider` function returns an asynchronous iterator that yields a single Resource object. The `.astart` method is called asynchronously when the resource is created, and the `.aclose` method is called asynchronously when the resource is released.

### Resource events

Sometimes, it can be useful to split the process of initializing and managing the lifecycle of an instance into separate providers.

```python
from typing import Iterator

from anydi import Container


class Client:
    def __init__(self) -> None:
        self.started = False
        self.closed = False

    def start(self) -> None:
        self.started = True

    def close(self) -> None:
        self.closed = True


container = Container()


@container.provider(scope="singleton")
def client_provider() -> Client:
    return Client()


@container.provider(scope="singleton")
def client_lifespan(client: Client) -> t.Iterator[None]:
    client.start()
    yield
    client.close()


client = container.resolve(Client)

assert not client.started
assert not client.closed

container.start()

assert client.started
assert not client.closed

container.close()

assert client.started
assert client.closed
```

!!! note

    This pattern can be used for both synchronous and asynchronous resources.

## Auto-Registration


`AnyDI` doesn't require explicit registration for every type. It can dynamically resolve and auto-register dependencies,
simplifying setups where manual registration for each type is impractical.

Consider a scenario with class dependencies:

```python
from anydi import singleton


@singleton
class Database:
    def connect(self) -> None:
        print("connect")
    def disconnect(self) -> None:
        print("disconnect")


@singleton
class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db


@singleton
class Service:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo
```

You can instantiate these classes without manually registering each one:

```python
from typing import Iterator

from anydi import Container

container = Container()

@container.provider(scope="singleton")
def db() -> Iterator[Database]:
    db = Database()
    db.connect()
    yield db
    db.disconnect()

# Retrieving an instance of Service
_ = container.resolve(Service)

assert container.is_resolved(Service)
assert container.is_resolved(Repository)
assert container.is_resolved(Database)
```

### Automatic Resource Management

When your class dependencies implement the context manager protocol by defining the `__enter__/__aenter__` and `__exit__/__aexit__` methods, these resources are automatically managed by the container for `singleton` and `request` scoped providers.

```python
from anydi import Container, singleton


@singleton
class Connection:
    def __init__(self) -> None:
        self.connected = False
        self.disconnected = False

    def __enter__(self) -> None:
        self.connected = True

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.connected = False
        self.disconnected = True


container = Container()
connection = container.resolve(Connection)

assert container.is_resolved(Connection)
assert connection.connected

container.close()

assert connection.disconnected
```

## Overriding Providers

Sometimes it's necessary to override a provider with a different implementation. To do this, you can register the provider with the override=True property set.

For example, suppose you have registered a singleton provider for a storage service:

```python
from anydi import Container


class StorageService:
    def __init__(self, backend: str) -> None:
        self.backend = backend

    def save(self, key: str, data: bytes) -> None:
        print(f"Saving to {self.backend}: {key}")


container = Container()


@container.provider(scope="singleton")
def local_storage() -> StorageService:
    return StorageService(backend="local")


@container.provider(scope="singleton", override=True)
def cloud_storage() -> StorageService:
    return StorageService(backend="s3")


service = container.resolve(StorageService)
assert service.backend == "s3"
```

Note that if you try to register the provider without passing the override parameter as True, it will raise an error:

```python
@container.provider(scope="singleton")  # will raise an error
def azure_storage() -> StorageService:
    return StorageService(backend="azure")
```


## Injecting Dependencies

In order to use the dependencies that have been provided to the `Container`, they need to be injected into the functions or classes that require them. This can be done by using the `@container.inject` decorator.

Here's an example of how to use the `@container.inject` decorator:

```python
from anydi import Container, Inject


class Service:
    def __init__(self, name: str) -> None:
        self.name = name


container = Container()


@container.provider(scope="singleton")
def service() -> Service:
    return Service(name="demo")


@container.inject
def handler(service: Service = Inject()) -> None:
    print(f"Hello, from service `{service.name}`")
```

Note that the service argument in the handler function has been given a default value of the `Inject()` marker. This lets `AnyDI` know which dependency to inject when the handler function is called.

Once the dependencies have been injected, the function can be called as usual, like so:

```python
handler()
```

You can also call the callable object with injected dependencies using the `run` method of the `Container` instance:

```python
from anydi import Container, Provide


class Service:
    def __init__(self, name: str) -> None:
        self.name = name


container = Container()


@container.provider(scope="singleton")
def service() -> Service:
    return Service(name="demo")


def handler(service: Provide[Service]) -> None:
    print(f"Hello, from service `{service.name}`")


container.run(handler)
```

In this case, the `run` method will automatically inject the dependencies and call the handler function. Using `@container.inject` is not necessary in this case.

#### Annotation Equivalents

AnyDI recognizes the following forms as equivalent ways to declare an injected dependency:

```python
dependency: MyType = Inject()
dependency: Annotated[MyType, Inject()]
dependency: Provide[MyType]
```

Choose whichever aligns with the framework or style you are using; they all resolve to the same provider lookup.


### Scanning Injections

`AnyDI` provides a simple way to inject dependencies by scanning Python modules or packages.
For example, your application might have the following structure:

```
/app
  api/
    handlers.py
  main.py
  services.py
```

`services.py` defines a service class:

```python
class Service:
    def __init__(self, name: str) -> None:
        self.name = name
```

`handlers.py` uses the Service class:

```python
from anydi import Inject, injectable

from app.services import Service


@injectable
def my_handler(service: Service = Inject()) -> None:
    print(f"Hello, from service `{service.name}`")
```

`main.py` starts the DI container and scans the app `handlers.py` module:

```python
from anydi import Container

from app.services import Service

container = Container()


@container.provider(scope="singleton")
def service() -> Service:
    return Service(name="demo")


container.scan(["app.handlers"])
container.start()

# application context

container.close()
```

The scan method takes a list of directory paths as an argument and recursively searches those directories for Python modules containing `@inject`-decorated functions or classes.

### Scanning Injections by tags

You can also scan for providers or injectables in specific tags. To do so, you need to use the tags argument when registering providers or injectables. For example:

```python
from anydi import Container

container = Container()
container.scan(["app.handlers"], tags=["tag1"])
```

This will scan for `@injectable` annotated target only with defined `tags` within the `app.handlers` module.


## Modules

`AnyDI` provides a way to organize your code and configure dependencies for the dependency injection container.
A module is a class that extends the `Module` base class and contains the configuration for the container.

Here's an example how to create and register simple module:

```python
from anydi import Container, Module, provider


class Repository:
    pass


class Service:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo


class AppModule(Module):
    def configure(self, container: Container) -> None:
        container.register(Repository)

    @provider(scope="singleton")
    def service(self, repo: Repository) -> Service:
        return Service(repo=repo)


container = Container(modules=[AppModule()])

# or
# container.register_module(AppModule())

assert container.is_registered(Service)
assert container.is_registered(Repository)
```

With `AnyDI`'s Modules, you can keep your code organized and easily manage your dependencies.


## Testing

To use `AnyDI` with your testing framework, call the `.override(interface=..., instance=...)` context manager
to temporarily replace a dependency with an overridden instance during testing. This allows you to isolate the code being tested from its dependencies.
The with `container.override()` context manager ensures that the overridden instance is used only within the context of the with block.
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

### Pytest Plugin

`AnyDI` provides a pytest plugin that automatically injects dependencies into test functions, eliminating boilerplate code and making tests cleaner.

#### Configuration

##### Container Setup

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

##### Auto-Injection Mode

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

#### Usage

##### Basic Injection

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

##### Fixture Priority

Pytest fixtures always take priority over dependency injection. If a pytest fixture and the `@pytest.mark.inject` decorator both provide a value for the same parameter name, the fixture value will be used.

##### Fixture Injection

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

##### Testing with `.create()`

For more control over dependency injection in tests, use the `.create()` method to instantiate classes with overridden dependencies:

```python
def test_handler(container: Container) -> None:
    repo_mock = mock.Mock(spec=Repository)
    repo_mock.all.return_value = [Item(name="mock1"), Item(name="mock2")]

    service = container.create(Service, repo=repo_mock)

    assert service.get_items() == [Item(name="mock1"), Item(name="mock2")]
```

## Conclusion

Check [examples](examples/basic.md) which shows how to use `AnyDI` in real-life application.
