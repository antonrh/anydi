# Core Concepts

Learn these basic concepts to use AnyDI better.

## Container

The `Container` is the main place where all your dependencies are stored. It keeps providers and creates dependencies when you need them.

```python
from anydi import Container

container = Container()
```

You can think of container as a registry that knows how to create and manage all your services.

### What container does:
- Stores provider registrations
- Resolves dependencies on demand
- Manages object lifecycles (singleton, transient, request)
- Performs dependency injection

## Provider

A provider is a function or class that creates an object of a specific type. It tells the container how to create a dependency. In the code, this is referred to as the `factory`.

```python
from anydi import Container


class EmailService:
    def send(self, to: str, message: str) -> None:
        print(f"Sending to {to}: {message}")


container = Container()


# Function provider (factory)
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

A scope controls the lifecycle of a dependency. It decides how long an instance lives and when it is created.

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

### Built-in scopes:
- **singleton**: Created one time and used everywhere
- **transient**: New instance created every time you need it
- **request**: Created one time per request context

### Custom scopes:
You can create your own scopes for special cases like background jobs, user sessions, or multi-tenancy.

## Dependency Injection

Dependency injection means that dependencies are given to a function or class automatically. You don't need to create them manually.

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

### Why use dependency injection:
- **Testability**: Easy to substitute mocks and test doubles
- **Flexibility**: Can swap implementations without modifying code
- **Maintainability**: Explicit dependencies make code easier to understand
- **Decoupling**: Services don't need to know dependency instantiation logic

## Dependency Type

A dependency type is a type annotation that identifies a dependency. Usually it is a class, but it can be any type. In the container, it's represented as the `dependency_type`.

```python
from typing import Protocol


# Protocol-based type
class StorageBackend(Protocol):
    def save(self, key: str, data: bytes) -> None: ...
    def load(self, key: str) -> bytes: ...


# Concrete implementation
class LocalStorage:
    def save(self, key: str, data: bytes) -> None:
        ...

    def load(self, key: str) -> bytes:
        ...


# Register implementation for dependency type
container.register(StorageBackend, lambda: LocalStorage(), scope="singleton")
```

### Named dependency types:
You can use `Annotated` to register multiple providers for the same type:

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

Resolution is the process when container creates an instance with all its dependencies.

```python
# Resolve a service
service = container.resolve(EmailService)
```

### Automatic vs manual resolution:
```python
# Manual resolution
service = container.resolve(EmailService)

# Automatic resolution
def send_welcome(service: Provide[EmailService]):
    service.send("user@example.com", "Welcome")

container.run(send_welcome)
```

## Lifecycle Management

Lifecycle management controls when resources are created, used, and cleaned up.

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

### Context managers:
AnyDI works with Python's context managers:

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

## How it all works together

Here is an example that shows how all concepts work together:

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
