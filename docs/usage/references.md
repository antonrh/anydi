# References

`container.ref()` returns a lazy reference to a dependency. It behaves like the dependency itself, but resolves it on first attribute access. Use it in plain functions that you do not want to decorate or run through the container. When the container itself is out of reach, use the [global container](global-container.md).

## Example

```python
from anydi import Container


class GreetingService:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"


container = Container()


@container.provider(scope="singleton")
def greeting_service() -> GreetingService:
    return GreetingService()


service = container.ref(GreetingService)


def greet() -> str:
    return service.greet("World")


assert greet() == "Hello, World!"
```

The reference is a transparent proxy. Attribute access, method calls, `isinstance()` and operators go to the real instance.

Nothing is resolved until the first attribute access. You can create a reference before its provider is registered.

A reference takes whatever `resolve()` takes, including [named providers](providers/annotated.md) and [type aliases](providers/basics.md#type-aliases).

## Caching

Singleton instances are cached inside the reference. The cache is dropped when the container state changes: on `override()`, `reset()`, `release()`, provider re-registration or container close.

Scoped dependencies, both `request` and custom scopes, are never cached. The reference resolves them on every access, so instances never leak between contexts.

Pass `cache=False` to resolve a singleton on every access:

```python
service = container.ref(GreetingService, cache=False)
```

## Transient dependencies

A reference needs an instance to refer to. A transient provider creates a new instance on every resolve, so `ref()` rejects it:

```python
import uuid


class RequestTracker:
    def __init__(self) -> None:
        self.request_id = str(uuid.uuid4())


@container.provider(scope="transient")
def request_tracker() -> RequestTracker:
    return RequestTracker()


tracker = container.ref(RequestTracker)  # TypeError
```

Register the dependency as a singleton if it is stateless. If you need a fresh instance per call, use a factory:

```python
from functools import partial


new_tracker = partial(container.resolve, RequestTracker)


def handle() -> str:
    tracker = new_tracker()
    return tracker.request_id


assert handle() != handle()
```

## Asynchronous dependencies

A reference is resolved synchronously. `ref()` rejects asynchronous providers right away, instead of failing later on access:

```python
container = Container()


@container.provider(scope="singleton")
async def greeting_service() -> GreetingService:
    return GreetingService()


service = container.ref(GreetingService)  # TypeError
```

Dependencies of the referenced provider are checked too. References created before their providers are registered are checked again by `build()`.

If a dependency needs asynchronous setup, keep its provider synchronous and move the setup into a resource:

```python
from collections.abc import AsyncIterator

from anydi import Container


class Database:
    def __init__(self) -> None:
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False


container = Container()


@container.provider(scope="singleton")
def get_db() -> Database:
    return Database()


@container.provider(scope="singleton")
async def db_lifespan(db: Database) -> AsyncIterator[None]:
    await db.connect()
    yield
    await db.disconnect()


db = container.ref(Database)


async def main() -> None:
    async with container:
        assert db.connected

    assert not db.connected
```

The resource is started by `astart()` and closed by `aclose()`. The database itself stays synchronous, so the reference keeps working.

## Testing

A reference always asks the container for the current instance, so `override()` is picked up. See [Testing](testing.md#overriding-lazy-references).
