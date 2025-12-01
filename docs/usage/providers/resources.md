# Resource Management

Resource providers are special types of providers that need to be started and stopped. This is useful for managing database connections, file handles, network sockets, or any other resources that require proper cleanup.

`AnyDI` supports both synchronous and asynchronous resource providers.

## Synchronous Resources

Here is an example of a synchronous resource provider that manages the lifecycle of a Resource object:

```python
from typing import Iterator

from anydi import Container


class DatabaseConnection:
    def __init__(self, name: str) -> None:
        self.name = name
        self.connected = False

    def connect(self) -> None:
        print(f"Connecting to {self.name}")
        self.connected = True

    def disconnect(self) -> None:
        print(f"Disconnecting from {self.name}")
        self.connected = False


container = Container()


@container.provider(scope="singleton")
def database_provider() -> Iterator[DatabaseConnection]:
    db = DatabaseConnection(name="postgres")
    db.connect()
    yield db
    db.disconnect()


# Start all resources
container.start()

# Use the resource
db = container.resolve(DatabaseConnection)
assert db.name == "postgres"
assert db.connected

# Close all resources
container.close()
```

In this example, the `database_provider` function returns an iterator that yields a single `DatabaseConnection` object. The `.connect()` method is called when the resource is created, and the `.disconnect()` method is called when the resource is released.

## Asynchronous Resources

Here is an example of an asynchronous resource provider that manages the lifecycle of an asynchronous Resource object:

```python
import asyncio
from typing import AsyncIterator

from anydi import Container


class AsyncDatabase:
    def __init__(self, name: str) -> None:
        self.name = name
        self.connected = False

    async def connect(self) -> None:
        print(f"Async connecting to {self.name}")
        # Simulate async connection
        await asyncio.sleep(0.1)
        self.connected = True

    async def disconnect(self) -> None:
        print(f"Async disconnecting from {self.name}")
        await asyncio.sleep(0.1)
        self.connected = False


container = Container()


@container.provider(scope="singleton")
async def async_database_provider() -> AsyncIterator[AsyncDatabase]:
    db = AsyncDatabase(name="postgres")
    await db.connect()
    yield db
    await db.disconnect()


async def main() -> None:
    # Start all resources
    await container.astart()

    # Use the resource
    db = await container.aresolve(AsyncDatabase)
    assert db.name == "postgres"
    assert db.connected

    # Close all resources
    await container.aclose()


asyncio.run(main())
```

In this example, the `async_database_provider` function returns an asynchronous iterator that yields a single `AsyncDatabase` object. The `.astart()` method is called asynchronously when the resource is created, and the `.aclose()` method is called asynchronously when the resource is released.

## Resource Events

Sometimes, it can be useful to split the process of initializing and managing the lifecycle of an instance into separate providers. This allows you to keep instance creation separate from lifecycle management.

```python
from typing import Iterator

from anydi import Container


class HTTPClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.started = False
        self.closed = False

    def start(self) -> None:
        print(f"Starting HTTP client for {self.base_url}")
        self.started = True

    def close(self) -> None:
        print(f"Closing HTTP client for {self.base_url}")
        self.closed = True


container = Container()


# Provider for creating the instance
@container.provider(scope="singleton")
def http_client() -> HTTPClient:
    return HTTPClient(base_url="https://api.example.com")


# Separate provider for managing lifecycle
@container.provider(scope="singleton")
def http_client_lifespan(client: HTTPClient) -> Iterator[None]:
    client.start()
    yield
    client.close()


# Resolve the client (not started yet)
client = container.resolve(HTTPClient)
assert not client.started
assert not client.closed

# Start resources
container.start()
assert client.started
assert not client.closed

# Close resources
container.close()
assert client.started
assert client.closed
```

!!! note
    This pattern can be used for both synchronous and asynchronous resources.

## Automatic Resource Management

When your class dependencies implement the context manager protocol by defining the `__enter__/__aenter__` and `__exit__/__aexit__` methods, these resources are automatically managed by the container for `singleton` and `request` scoped providers.

```python
from anydi import Container, singleton


@singleton
class Connection:
    def __init__(self) -> None:
        self.connected = False
        self.disconnected = False

    def __enter__(self):
        print("Entering context")
        self.connected = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("Exiting context")
        self.connected = False
        self.disconnected = True


container = Container()
connection = container.resolve(Connection)

assert container.is_resolved(Connection)
assert connection.connected

container.close()

assert connection.disconnected
```

## Best Practices

1. **Always clean up resources**: Use resource providers to ensure proper cleanup of connections, files, and other resources
2. **Match async patterns**: Use async resource providers (`AsyncIterator`) for async resources
3. **Separate concerns**: Consider using separate providers for instance creation and lifecycle management
4. **Test resource cleanup**: Ensure your tests verify that resources are properly closed

---

**Related Topics:**
- [Provider Basics](basics.md) - Learn basic provider registration
- [Scopes](../scopes.md) - Understand when resources are initialized and cleaned up
- [Auto-Registration](auto-registration.md) - Learn about automatic context manager support
