# Dependency Injection

To use dependencies from the `Container`, you need to inject them into functions or classes. The recommended way is using the `Provide` annotation with `container.run()`.

Here is the basic example:

```python
from anydi import Container, Provide


class Service:
    def __init__(self, name: str) -> None:
        self.name = name


container = Container()


@container.provider(scope="singleton")
def service() -> Service:
    return Service(name="demo")


def handler(service: Provide[Service]) -> None:
    print(f"Hello, from service `{service.name}`")


container.run(handler)
```

The `run` method automatically injects dependencies and calls the function.

You can also use the `@container.inject` decorator with `Inject()` marker:

```python
from anydi import Container, Inject


class Service:
    def __init__(self, name: str) -> None:
        self.name = name


container = Container()


@container.provider(scope="singleton")
def service() -> Service:
    return Service(name="demo")


@container.inject
def handler(service: Service = Inject()) -> None:
    print(f"Hello, from service `{service.name}`")


# After dependencies are injected, call the function normally
handler()
```

The service argument has a default value `Inject()`. This tells `AnyDI` which dependency to inject when you call the handler function.

## Annotation Equivalents

`AnyDI` understands these different ways to declare injected dependency (they all work the same):

```python
dependency: MyType = Inject()
dependency: Annotated[MyType, Inject()]
dependency: Provide[MyType]
```

You can use any of these forms. They all do the same thing.

## Lazy References

`container.ref()` returns a lazy reference to a dependency. Use it in plain functions that you do not want to decorate or run through the container.

The container still owns the dependency: its provider, its scope and its lifespan do not change. Only the way your code reaches it does. Injection and lazy references are two styles of the same thing, pick whichever reads better in your application.

### Example

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

### Named dependencies

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

### Caching

Singleton instances are cached inside the reference. The cache is dropped when the container state changes: on `override()`, `reset()`, `release()`, provider re-registration or container close.

Scoped dependencies, both `request` and custom scopes, are never cached. The reference resolves them on every access, so instances never leak between contexts.

Pass `cache=False` to resolve a singleton on every access:

```python
service = container.ref(GreetingService, cache=False)
```

### Testing

A reference always asks the container for the current instance, so `override()` is picked up. See [Testing](testing.md#overriding-lazy-references).

### Transient dependencies

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

Without that check, every attribute access would read a different instance, and `tracker.request_id` would change between two lines of the same function.

Register the dependency as a singleton if it is stateless. If you need a fresh instance per call, use a factory:

```python
from functools import partial


new_tracker = partial(container.resolve, RequestTracker)


def handle() -> str:
    tracker = new_tracker()
    return tracker.request_id


assert handle() != handle()
```

### Asynchronous dependencies

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

## Scanning Injections

`AnyDI` can scan Python modules or packages to find and inject dependencies automatically.
Your application might look like this:

```
/app
  api/
    handlers.py
  main.py
  services.py
```

`services.py` defines a service class:

```python
class Service:
    def __init__(self, name: str) -> None:
        self.name = name
```

`handlers.py` uses the Service class:

```python
from anydi import Provide, injectable

from app.services import Service


@injectable
def my_handler(service: Provide[Service]) -> None:
    print(f"Hello, from service `{service.name}`")


# You can also use Inject() marker:
# from anydi import Inject
# @injectable
# def my_handler(service: Service = Inject()) -> None:
#     print(f"Hello, from service `{service.name}`")
```

`main.py` starts the DI container and scans the app `handlers.py` module:

```python
from anydi import Container

from app.services import Service

container = Container()


@container.provider(scope="singleton")
def service() -> Service:
    return Service(name="demo")


container.scan(["app.handlers"])
container.start()

# application context

container.close()
```

The scan method takes a list of module paths and searches them for functions or classes with `@inject` decorator.

## Scanning by tags

You can scan for specific tags only. Use the tags argument like this:

```python
from anydi import Container

container = Container()
container.scan(["app.handlers"], tags=["tag1"])
```

This scans only `@injectable` items with the specified tags in the `app.handlers` module.

## Ignoring packages during scan

Use the `ignore` parameter to exclude specific packages or modules from scanning. This helps avoid circular imports or infinite loops when modules have complex import dependencies:

```python
from anydi import Container

container = Container()
container.scan("app", ignore=["app.tests", "app.migrations"])
```

See [Auto-Registration - Ignoring packages](providers/auto-registration.md#ignoring-packages) for more details.
