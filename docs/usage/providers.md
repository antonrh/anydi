# Providers

Providers are the backbone of `AnyDI`. A provider is a function or a class that returns an instance of a specific type.
Once a provider is registered with `Container`, it can be used to resolve dependencies throughout the application.

## Registering Providers

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

## Annotated Providers

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

## Unregistering Providers

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

## Resolved Providers

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
def resource_provider() -> Iterator[Resource]:
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

### Resource Events

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
def client_lifespan(client: Client) -> Iterator[None]:
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

## Overriding Providers

Sometimes it's necessary to override a provider with a different implementation. To do this, you can register the provider with the `override=True` flag.

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

If you try to register a conflicting provider without `override=True`, the container raises an error:

```python
@container.provider(scope="singleton")  # will raise an error
def azure_storage() -> StorageService:
    return StorageService(backend="azure")
```

## Auto-Registration

`AnyDI` doesn't require explicit registration for every type. It can dynamically resolve and auto-register dependencies, which helps when manually registering every class is impractical.

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
