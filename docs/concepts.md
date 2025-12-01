# Core Concepts

Understanding these core concepts will help you make the most of AnyDI.

## Container

The `Container` is the central registry for all your dependencies. It stores providers and resolves dependencies when needed.

```python
from anydi import Container

container = Container()
```

Think of the container as a "registry" or "service locator" that knows how to create and manage all your application's services.

### Key Responsibilities:
- Stores provider registrations
- Resolves dependencies
- Manages lifecycles (singleton, transient, request)
- Handles dependency injection

## Provider

A provider is a callable (function or class) that creates an instance of a specific type. It tells the container *how* to create a dependency.

```python
from anydi import Container


class EmailService:
    def send(self, to: str, message: str) -> None:
        print(f"Sending to {to}: {message}")


container = Container()


# Function provider
@container.provider(scope="singleton")
def email_service() -> EmailService:
    return EmailService()


# Class provider (auto-registration)
from anydi import singleton

@singleton
class NotificationService:
    def __init__(self, email: EmailService) -> None:
        self.email = email
```

### Types of Providers:
- **Function providers**: Functions decorated with `@container.provider()`
- **Class providers**: Classes decorated with `@singleton`, `@transient`, or `@request`
- **Resource providers**: Generators that manage lifecycle

## Scope

A scope determines the lifecycle of a dependency - how long an instance lives and when it's created.

```python
# Singleton: One instance for the entire application
@container.provider(scope="singleton")
def config() -> Config:
    return Config()

# Transient: New instance every time
@container.provider(scope="transient")
def request_handler() -> Handler:
    return Handler()

# Request: One instance per request context
@container.provider(scope="request")
def user_context() -> UserContext:
    return UserContext()
```

### Built-in Scopes:
- **singleton**: Created once, shared everywhere
- **transient**: Created every time it's requested
- **request**: Created once per request context

### Custom Scopes:
You can define your own scopes for specialized use cases like background jobs, user sessions, or multi-tenancy.

## Dependency Injection

Dependency injection is the process of automatically providing dependencies to a function or class, rather than requiring them to create or find dependencies themselves.

```python
from anydi import Provide


# Without DI (manual)
def process_order_manual():
    db = Database()  # Manually create
    repo = OrderRepository(db)  # Manually wire
    service = OrderService(repo)  # Manually wire
    service.process()


# With DI (automatic)
def process_order(service: Provide[OrderService]) -> None:
    service.process()  # Dependencies injected automatically


container.run(process_order)
```

### Benefits:
- **Testability**: Easy to substitute mocks in tests
- **Flexibility**: Change implementations without changing code
- **Maintainability**: Clear dependencies make code easier to understand
- **Decoupling**: Services don't need to know how to create their dependencies

## Interface

An interface is the type annotation used to identify a dependency. It's typically a class, but can be any type.

```python
from typing import Protocol


# Protocol-based interface
class StorageBackend(Protocol):
    def save(self, key: str, data: bytes) -> None: ...
    def load(self, key: str) -> bytes: ...


# Concrete implementation
class LocalStorage:
    def save(self, key: str, data: bytes) -> None:
        ...

    def load(self, key: str) -> bytes:
        ...


# Register implementation for interface
container.register(StorageBackend, lambda: LocalStorage(), scope="singleton")
```

### Named Interfaces:
Use `Annotated` to register multiple providers for the same type:

```python
from typing import Annotated


@container.provider(scope="singleton")
def primary_db() -> Annotated[Database, "primary"]:
    return Database(host="primary")


@container.provider(scope="singleton")
def replica_db() -> Annotated[Database, "replica"]:
    return Database(host="replica")
```

## Resolution

Resolution is the process of creating an instance along with all its dependencies.

```python
# Resolve a service
service = container.resolve(EmailService)

# Resolution process:
# 1. Container looks up the provider for EmailService
# 2. Checks if dependencies are needed (from type hints)
# 3. Recursively resolves each dependency
# 4. Creates the instance
# 5. Caches it (if scope requires)
# 6. Returns the instance
```

### Automatic vs Manual Resolution:
```python
# Manual resolution
service = container.resolve(EmailService)

# Automatic resolution (via injection)
@container.inject
def send_email(service: EmailService = Inject()):
    service.send("user@example.com", "Hello")

# Automatic resolution (via Provide)
def send_welcome(service: Provide[EmailService]):
    service.send("user@example.com", "Welcome")

container.run(send_welcome)
```

## Lifecycle Management

Lifecycle management refers to controlling when resources are created, used, and cleaned up.

```python
from typing import Iterator


@container.provider(scope="singleton")
def database_connection() -> Iterator[Database]:
    # Setup
    db = Database()
    db.connect()

    # Provide the resource
    yield db

    # Cleanup
    db.disconnect()


# Start resources
container.start()

# Use resources
db = container.resolve(Database)

# Cleanup resources
container.close()
```

### Context Managers:
AnyDI integrates with Python's context manager protocol:

```python
# Singleton context
with container:
    # Resources are started
    service = container.resolve(Service)
    # Resources are closed on exit

# Request context
with container.request_context():
    # Request-scoped resources are created
    user = container.resolve(UserContext)
    # Request-scoped resources are cleaned up on exit
```

## Putting It All Together

Here's how all these concepts work together:

```python
from typing import Iterator
from anydi import Container, Provide, singleton


# 1. Define services with dependencies
@singleton
class Database:
    def query(self, sql: str) -> list:
        return []


class UserRepository:
    def __init__(self, db: Database) -> None:  # Dependency via __init__
        self.db = db


# 2. Create container
container = Container()


# 3. Register provider with lifecycle
@container.provider(scope="singleton")
def db() -> Iterator[Database]:
    db = Database()
    print("Connecting...")
    yield db
    print("Disconnecting...")


# 4. Register repository
container.register(UserRepository, scope="singleton")


# 5. Use dependency injection
def get_users(repo: Provide[UserRepository]) -> list:  # Injected dependency
    return repo.db.query("SELECT * FROM users")


# 6. Run with lifecycle management
with container:
    users = container.run(get_users)
    print(users)
```

## Next Steps

- [Providers](usage/providers/index.md) - Learn more about providers
- [Scopes](usage/scopes.md) - Deep dive into scopes
- [Dependency Injection](usage/injection.md) - Master injection patterns
