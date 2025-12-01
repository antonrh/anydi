# Auto-Registration

`AnyDI` doesn't require explicit registration for every type. It can dynamically resolve and auto-register dependencies, which simplifies setups where manually registering every class is impractical.

## Basic Auto-Registration

Consider a scenario with class dependencies:

```python
from anydi import singleton


@singleton
class Database:
    def connect(self) -> None:
        print("Connecting to database")

    def disconnect(self) -> None:
        print("Disconnecting from database")


@singleton
class UserRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def find_user(self, user_id: int) -> dict:
        return {"id": user_id, "name": "Alice"}


@singleton
class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

    def get_user(self, user_id: int) -> dict:
        return self.repo.find_user(user_id)
```

You can instantiate these classes without manually registering each one. Simply register the root dependency (if needed) and the container will automatically resolve the entire dependency tree:

```python
from typing import Iterator

from anydi import Container

container = Container()


# Only register the Database with lifecycle management
@container.provider(scope="singleton")
def db() -> Iterator[Database]:
    db = Database()
    db.connect()
    yield db
    db.disconnect()


# Resolve UserService - Repository and Service are auto-registered
service = container.resolve(UserService)
user = service.get_user(123)

# Verify all dependencies were auto-registered
assert container.is_resolved(UserService)
assert container.is_resolved(UserRepository)
assert container.is_resolved(Database)
```

## Using Scope Decorators

The `@singleton`, `@transient`, and `@request` decorators mark classes for auto-registration with the specified scope:

```python
from anydi import Container, singleton, transient


@singleton
class ConfigService:
    def __init__(self) -> None:
        self.config = {"env": "production"}


@transient
class RequestHandler:
    def __init__(self, config: ConfigService) -> None:
        self.config = config

    def handle(self) -> str:
        return f"Handling request in {self.config.config['env']}"


container = Container()

# Auto-registration happens on first resolve
handler1 = container.resolve(RequestHandler)
handler2 = container.resolve(RequestHandler)

# ConfigService is singleton - same instance
assert handler1.config is handler2.config

# RequestHandler is transient - different instances
assert handler1 is not handler2
```

## Mixing Explicit and Auto-Registration

You can mix explicit registration with auto-registration:

```python
from anydi import Container, singleton


class EmailService:
    def send(self, to: str, message: str) -> None:
        print(f"Sending email to {to}: {message}")


@singleton
class NotificationService:
    def __init__(self, email: EmailService) -> None:
        self.email = email

    def notify(self, user: str, message: str) -> None:
        self.email.send(user, message)


container = Container()

# Explicitly register EmailService
container.register(EmailService, scope="singleton")

# NotificationService will be auto-registered when resolved
notifier = container.resolve(NotificationService)
notifier.notify("user@example.com", "Welcome!")
```

## Benefits of Auto-Registration

1. **Less Boilerplate**: No need to manually register every class in your dependency tree
2. **Maintainability**: Adding new dependencies doesn't require updating registration code
3. **Flexibility**: Easily override specific dependencies while letting others auto-register

## Limitations

1. **Explicit is Better**: For public APIs or library interfaces, explicit registration provides better documentation
2. **Circular Dependencies**: Auto-registration cannot resolve circular dependencies
3. **Scope Validation**: The scope decorator must match the expected usage pattern

## Best Practices

1. **Use decorators consistently**: Apply `@singleton`, `@transient`, or `@request` to classes that should be auto-registered
2. **Register roots explicitly**: Register root dependencies (like databases, config) with proper lifecycle management
3. **Document auto-registered classes**: Make it clear which classes are auto-registered vs explicitly configured
4. **Test resolution**: Ensure all dependencies resolve correctly, especially in complex trees

---

**Related Topics:**
- [Provider Basics](basics.md) - Learn explicit provider registration
- [Resource Management](resources.md) - Manage lifecycle of auto-registered resources
- [Scopes](../scopes.md) - Understand scope decorators
