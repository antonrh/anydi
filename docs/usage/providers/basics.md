# Provider Basics

Providers are the main part of `AnyDI`. A provider is a function or class that returns an instance of a specific type.
After you register a provider with `Container`, you can use it to resolve dependencies in your application.

## Registering providers

To register a provider, use the `register` method of the `Container`. The method takes the `dependency_type` (the type of the object) and the `factory` (the provider function or class), and a `scope`.

If the `factory` is not provided, the `dependency_type` itself is used as the factory (e.g., when registering a class).

```python
from anydi import Container


class EmailService:
    def send(self, to: str, subject: str) -> None:
        print(f"Sending email to {to}: {subject}")


container = Container()

# Explicitly using argument names
container.register(dependency_type=EmailService, scope="singleton")

# Using positional arguments (recommended)
container.register(EmailService, scope="singleton")

service = container.resolve(EmailService)
service.send("user@example.com", "Welcome!")
```

You can also use the `@provider` decorator to register a provider function. The decorator registers the provider with `Container` automatically.

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

## Unregistering providers

To unregister a provider, use the `unregister` method of the `Container`. The method takes the dependency type you want to remove.

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

## Checking provider status

### Checking registration

To check if a provider is registered, use the `is_registered` method:

```python
from anydi import Container


class LoggerService:
    def log(self, message: str) -> None:
        print(f"[LOG] {message}")


container = Container()

# Before registration
assert not container.is_registered(LoggerService)

# Register the provider
container.register(LoggerService, scope="singleton")

# After registration
assert container.is_registered(LoggerService)
```

### Checking resolution

To check if a provider has a resolved instance, use the `is_resolved` method of the `Container`. This method takes the dependency type.

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

## Releasing instances

To release a provider instance, use the `release` method of the `Container`. This method takes the dependency type. You can also reset all instances with the `reset` method.

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

---

**Next Steps:**
- [Named Providers](annotated.md) - Learn how to register multiple providers for the same type
- [Resource Management](resources.md) - Understand lifecycle management for resources
- [Scopes](../scopes.md) - Learn about different provider scopes
