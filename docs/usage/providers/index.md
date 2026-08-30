# Providers

This section covers how to register providers, name several of one type, hand out resources that need closing, and let `AnyDI` register classes for you. [Provider basics](basics.md) starts from what a provider is.

## Quick examples

### Basic provider
```python
from anydi import Container

container = Container()

@container.provider(scope="singleton")
def config() -> dict:
    return {"env": "production"}
```

### Named provider
```python
from typing import Annotated

@container.provider(scope="singleton")
def primary_db() -> Annotated[Database, "primary"]:
    return Database(host="primary.db")
```

### Resource provider
```python
from typing import Iterator

@container.provider(scope="singleton")
def database() -> Iterator[Database]:
    db = Database()
    db.connect()
    yield db
    db.disconnect()
```

### Auto-Registered provider
```python
from anydi import singleton

@singleton
class UserService:
    def __init__(self, db: Database) -> None:
        self.db = db
```

## Learn more

- **[Provider Basics](basics.md)** - Register, unregister, and check provider status
- **[Named Providers](annotated.md)** - Register multiple providers for the same type
- **[Resource Management](resources.md)** - Manage lifecycle of resources like databases and connections
- **[Auto-Registration](auto-registration.md)** - Automatically register dependencies with decorators

---

**Next Steps:**
- [Scopes](../scopes.md) - Learn about provider lifecycles
- [Dependency Injection](../injection.md) - Learn how to inject providers
- [Testing](../testing.md) - Learn how to test with providers
