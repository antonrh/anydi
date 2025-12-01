# Named Providers

Sometimes, it's useful to register multiple providers for the same type. For example, you might want to register multiple database connections or different implementations of the same interface. This can be achieved by using the `Annotated` type hint with a string argument to distinguish between providers.

## Basic Usage

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


# Resolve specific providers by name
primary = container.resolve(Annotated[DatabaseConnection, "primary"])
replica = container.resolve(Annotated[DatabaseConnection, "replica"])

assert primary.host == "db-primary.local"
assert replica.host == "db-replica.local"
```

In this code example, we define two providers for different database connections. The `Annotated` type hint with string argument allows you to specify which provider to retrieve based on the name provided within the annotation.

## Use Cases

### Multiple Configurations

```python
from typing import Annotated

from anydi import Container


class APIClient:
    def __init__(self, base_url: str, timeout: int) -> None:
        self.base_url = base_url
        self.timeout = timeout


container = Container()


@container.provider(scope="singleton")
def production_api() -> Annotated[APIClient, "production"]:
    return APIClient(base_url="https://api.production.com", timeout=30)


@container.provider(scope="singleton")
def staging_api() -> Annotated[APIClient, "staging"]:
    return APIClient(base_url="https://api.staging.com", timeout=60)


# Use different API clients based on context
prod_client = container.resolve(Annotated[APIClient, "production"])
staging_client = container.resolve(Annotated[APIClient, "staging"])
```

### Different Implementations

```python
from typing import Annotated, Protocol

from anydi import Container


class StorageBackend(Protocol):
    def save(self, key: str, data: bytes) -> None: ...
    def load(self, key: str) -> bytes: ...


class LocalStorage:
    def save(self, key: str, data: bytes) -> None:
        print(f"Saving to local: {key}")

    def load(self, key: str) -> bytes:
        return b"local_data"


class S3Storage:
    def save(self, key: str, data: bytes) -> None:
        print(f"Saving to S3: {key}")

    def load(self, key: str) -> bytes:
        return b"s3_data"


container = Container()


@container.provider(scope="singleton")
def local_storage() -> Annotated[StorageBackend, "local"]:
    return LocalStorage()


@container.provider(scope="singleton")
def s3_storage() -> Annotated[StorageBackend, "s3"]:
    return S3Storage()


# Choose storage backend based on requirements
local = container.resolve(Annotated[StorageBackend, "local"])
cloud = container.resolve(Annotated[StorageBackend, "s3"])
```

## Best Practices

1. **Use descriptive names**: Choose clear, meaningful names that indicate the purpose or configuration of each provider
2. **Document naming conventions**: Make it clear to other developers which names are available and what they represent
3. **Avoid over-complication**: If you find yourself registering many named variants, consider whether a different design pattern might be more appropriate

---

**Related Topics:**
- [Provider Basics](basics.md) - Learn basic provider registration
- [Testing](../testing.md) - Learn how to override providers for testing
- [Dependency Injection](../injection.md) - Learn how to inject named providers
