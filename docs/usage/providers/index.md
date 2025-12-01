# Providers

Providers are the backbone of `AnyDI`. A provider is a function or a class that returns an instance of a specific type. Once a provider is registered with `Container`, it can be used to resolve dependencies throughout the application.

## Quick Examples

### Basic Provider
```python
from anydi import Container

container = Container()

@container.provider(scope="singleton")
def config() -> dict:
    return {"env": "production"}
```

### Named Provider
```python
from typing import Annotated

@container.provider(scope="singleton")
def primary_db() -> Annotated[Database, "primary"]:
    return Database(host="primary.db")
```

### Resource Provider
```python
from typing import Iterator

@container.provider(scope="singleton")
def database() -> Iterator[Database]:
    db = Database()
    db.connect()
    yield db
    db.disconnect()
```

### Auto-Registered Provider
```python
from anydi import singleton

@singleton
class UserService:
    def __init__(self, db: Database) -> None:
        self.db = db
```

## Learn More

- **[Provider Basics](basics.md)** - Register, unregister, and check provider status
- **[Named Providers](annotated.md)** - Register multiple providers for the same type
- **[Resource Management](resources.md)** - Manage lifecycle of resources like databases and connections
- **[Auto-Registration](auto-registration.md)** - Automatically register dependencies with decorators

---

**Next Steps:**
- [Scopes](../scopes.md) - Learn about provider lifecycles
- [Dependency Injection](../injection.md) - Learn how to inject providers
- [Testing](../testing.md) - Learn how to test with providers
