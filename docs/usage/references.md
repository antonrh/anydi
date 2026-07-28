# References

`container.ref()` returns a lazy reference to a dependency. It behaves like the dependency itself, but resolves it on first attribute access. Use it in plain functions that you do not want to decorate or run through the container.

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

## Caching

Singleton instances are cached inside the reference. The cache is dropped when the container state changes: on `override()`, `reset()`, `release()`, provider re-registration or container close.

Scoped dependencies, both `request` and custom scopes, are never cached. The reference resolves them on every access, so instances never leak between contexts.

Pass `cache=False` to resolve a singleton on every access:

```python
service = container.ref(GreetingService, cache=False)
```

## Named dependencies

References work with [named providers](providers/annotated.md) and [type aliases](providers/basics.md#type-aliases):

```python
from typing import Annotated


class Database:
    def __init__(self, host: str) -> None:
        self.host = host


@container.provider(scope="singleton")
def primary_db() -> Annotated[Database, "primary"]:
    return Database(host="db-primary.local")


@container.provider(scope="singleton")
def replica_db() -> Annotated[Database, "replica"]:
    return Database(host="db-replica.local")


primary = container.ref(Annotated[Database, "primary"])
replica = container.ref(Annotated[Database, "replica"])

assert primary.host == "db-primary.local"
assert replica.host == "db-replica.local"
```

Each reference keeps its own name, so overriding one of them in tests leaves the other one alone.

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

## Global container

A module that the container imports cannot import the container back, so `container.ref()` is not available there. A decorator that needs a dependency is the usual case.

`create_global_container()` makes a container available process-wide, and `global_ref()` references a dependency without naming it.

```python
# app/adapters/cache.py
import functools
from typing import Protocol

from anydi import global_ref


class Cache(Protocol):
    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str) -> None: ...


cache = global_ref(Cache)


def cached(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        key = func.__qualname__

        if (value := cache.get(key)) is not None:
            return value

        value = func(*args, **kwargs)
        cache.set(key, value)
        return value

    return wrapper
```

```python
# app/container.py
from anydi import create_global_container

from app.adapters.cache import Cache, MemoryCache

container = create_global_container()


@container.provider(scope="singleton")
def cache_provider() -> Cache:
    return MemoryCache()
```

A global reference binds on first access, so the modules can be imported in any order. In everything else it behaves like `container.ref()`.

See the [example application](../examples/global_container.md) for the whole picture.

### Managing the container

```python
get_global_container()            # raises if it is not set
get_global_container_or_none()    # None instead of raising
set_global_container(container)   # register an existing container
reset_global_container()          # unset it, references bind again
```

There is one global container per process. `create_global_container()` raises if one is already set, so replacing it takes an explicit `reset_global_container()`.

Using a reference while the container is unset raises `RuntimeError` naming the dependency. The reference reports its state without resolving anything:

```python
<GlobalRef for app.adapters.cache.Cache, unbound>
```

### Testing with the global container

The pytest plugin makes the `container` fixture global, so references resolve against the container under test, `override()` included. A container created with `create_global_container()` is picked up by the fixture, which makes the `anydi_container` setting unnecessary.

Prefer `container.ref()` wherever the container can be reached, it says which container it belongs to.
