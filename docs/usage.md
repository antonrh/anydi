# Usage

## Providers

Providers are the backbone of `AnyDI`. A provider is a function or a class that returns an instance of a specific type.
Once a provider is registered with `Container`, it can be used to resolve dependencies throughout the application.

### Registering Providers

To register a provider, you can use the `register` method of the `Container` instance. The method takes
three arguments: the type of the object to be provided, the provider function or class, and a scope.

```python
from anydi import Container

container = Container()


def message() -> str:
    return "Hello, World!"


container.register(str, message, scope="singleton")

assert container.resolve(str) == "Hello, World!"
```

Alternatively, you can use the `@provider` decorator to register a provider function. The decorator takes care of registering the provider with `Container`.

```python
from anydi import Container

container = Container()


@container.provider(scope="singleton")
def message() -> str:
    return "Hello, World!"


assert container.resolve(str) == "Hello, World!"
```

### Annotated Providers

Sometimes, it's useful to register multiple providers for the same type. For example, you might want to register a provider for a string that returns a different message depending on the name of the provider. This can be achieved by using the `Annotated` type hint with the string argument:

```python
from typing import Annotated

from anydi import Container

container = Container()


@container.provider(scope="singleton")
def message1() -> Annotated[str, "message1"]:
    return "Message1"


@container.provider(scope="singleton")
def message2() -> Annotated[str, "message2"]:
    return "Message2"


assert container.resolve(Annotated[str, "message1"]) == "Message1"
assert container.resolve(Annotated[str, "message2"]) == "Message2"
```

In this code example, we define two providers, `message1` and `message2`, each returning a different message. The Annotated type hint with string argument allows you to specify which provider to retrieve based on the name provided within the annotation.

### Unregistering Providers

To unregister a provider, you can use the `unregister` method of the `Container` instance. The method takes
interface of the dependency to be unregistered.

```python
from anydi import Container

container = Container()


@container.provider(scope="singleton")
def message() -> str:
    return "Hello, World!"


assert container.is_registered(str)

container.unregister(str)

assert not container.is_registered(str)
```

### Resolved Providers

To check if a registered provider has a resolved instance, you can use the `is_resolved` method of the `Container` instance.
This method takes the interface of the dependency to be checked.

```python
from anydi import Container

container = Container()


@container.provider(scope="singleton")
def message() -> str:
    return "Hello, World!"


# Check if an instance is resolved
assert not container.is_resolved(str)

assert container.resolve(str) == "Hello, World!"

assert container.is_resolved(str)

container.release(str)

assert not container.is_resolved(str)
```

To release a provider instance, you can use the `release` method of the `Container` instance. This method takes the interface of the dependency to be reset. Alternatively, you can reset all instances with the `reset` method.

```python
from anydi import Container

container = Container()
container.register(str, lambda: "Hello, World!", scope="singleton")
container.register(int, lambda: 100, scope="singleton")

container.resolve(str)
container.resolve(int)

assert container.is_resolved(str)
assert container.is_resolved(int)

container.reset()

assert not container.is_resolved(str)
assert not container.is_resolved(int)
```

!!! note

    This pattern can be used while writing unit tests to ensure that each test case has a clean dependency graph.

## Auto-Registration


`AnyDI` doesn't require explicit registration for every type. It can dynamically resolve and auto-register dependencies,
simplifying setups where manual registration for each type is impractical.

Consider a scenario with class dependencies:

```python
class Database:
    def connect(self) -> None:
        print("connect")
    def disconnect(self) -> None:
        print("disconnect")


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db


class Service:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo
```

You can instantiate these classes without manually registering each one:

```python
from typing import Iterator

from anydi import Container

container = Container()

@container.provider(scope="singleton")
def db() -> Iterator[Database]:
    db = Database()
    db.connect()
    yield db
    db.disconnect()

# Retrieving an instance of Service
_ = container.resolve(Service)

assert container.is_resolved(Service)
assert container.is_resolved(Repository)
assert container.is_resolved(Database)
```

### Automatic Resource Management

When your class dependencies implement the context manager protocol by defining the `__enter__/__aenter__` and `__exit__/__aexit__` methods, these resources are automatically managed by the container for `singleton` and `request` scoped providers.

```python
from anydi import Container, singleton


@singleton
class Connection:
    def __init__(self) -> None:
        self.connected = False
        self.disconnected = False

    def __enter__(self) -> None:
        self.connected = True

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.connected = False
        self.disconnected = True


container = Container()
connection = container.resolve(Connection)

assert container.is_resolved(Connection)
assert connection.connected

container.close()

assert connection.disconnected
```

## Scopes

`AnyDI` supports three different scopes for providers:

* `transient`
* `singleton`
* `request`

### `transient` scope

Providers with transient scope create a new instance of the object each time it's requested. You can set the scope when registering a provider.

```python
import random

from anydi import Container

container = Container()


@container.provider(scope="transient")
def message() -> str:
    return random.choice(["hello", "hola", "ciao"])


print(container.resolve(str))  # will print random message
```

### `singleton` scope

Providers with singleton scope create a single instance of the object and return it every time it's requested.

```python
from anydi import Container


class Service:
    def __init__(self, name: str) -> None:
        self.name = name


container = Container()


@container.provider(scope="singleton")
def service() -> Service:
    return Service(name="demo")


assert container.resolve(Service) == container.resolve(Service)
```

### `request` scope

Providers with request scope create an instance of the object for each request. The instance is only available within the context of the request.

```python
from anydi import Container


class Request:
    def __init__(self, path: str) -> None:
        self.path = path


container = Container()


@container.provider(scope="request")
def request_provider() -> Request:
    return Request(path="/")


with container.request_context():
    assert container.resolve(Request).path == "/"

container.resolve(Request)  # this will raise LookupError
```

or using asynchronous request context:

```python
from anydi import Container

container = Container()


@container.provider(scope="request")
def request_provider() -> Request:
    return Request(path="/")


async def main() -> None:
    async with container.arequest_context():
        assert (await container.aresolve(Request).path) == "/"
```

#### `request` scoped instances

In `AnyDI`, you can create `request-scoped` instances to manage dependencies that should be instantiated per request.
This is particularly useful when handling dependencies with request-specific data that need to be isolated across different requests.

To create a request context, you use the `request_context` (or `arequest_context` for async) method on the container.
This context is then used to resolve dependencies scoped to the current request.

```python
from typing import Annotated

from anydi import Container

container = Container()


@container.provider(scope="request")
def request_param(request: Request) -> Annotated[str, "request.param"]:
    return request.param


with container.request_context() as ctx:
    ctx.set(Request, Request(param="param1"))

    assert container.resolve(Annotated[str, "request.param"]) == "param1"
```

## Resource Providers

Resource providers are special types of providers that need to be started and stopped. `AnyDI` supports synchronous and asynchronous resource providers.

### Synchronous Resources

Here is an example of a synchronous resource provider that manages the lifecycle of a Resource object:

```python
from typing import Iterator

from anydi import Container


class Resource:
    def __init__(self, name: str) -> None:
        self.name = name

    def start(self) -> None:
        print("start resource")

    def close(self) -> None:
        print("close resource")


container = Container()


@container.provider(scope="singleton")
def resource_provider() -> t.Iterator[Resource]:
    resource = Resource(name="demo")
    resource.start()
    yield resource
    resource.close()


container.start()  # start resources

assert container.resolve(Resource).name == "demo"

container.close()  # close resources
```

In this example, the resource_provider function returns an iterator that yields a single Resource object. The `.start` method is called when the resource is created, and the `.close` method is called when the resource is released.

### Asynchronous Resources

Here is an example of an asynchronous resource provider that manages the lifecycle of an asynchronous Resource object:

```python
import asyncio
from typing import AsyncIterator

from anydi import Container


class Resource:
    def __init__(self, name: str) -> None:
        self.name = name

    async def start(self) -> None:
        print("start resource")

    async def close(self) -> None:
        print("close resource")


container = Container()


@container.provider(scope="singleton")
async def resource_provider() -> AsyncIterator[Resource]:
    resource = Resource(name="demo")
    await resource.start()
    yield resource
    await resource.close()


async def main() -> None:
    await container.astart()  # start resources

    assert (await container.aresolve(Resource)).name == "demo"

    await container.aclose()  # close resources


asyncio.run(main())
```

In this example, the `resource_provider` function returns an asynchronous iterator that yields a single Resource object. The `.astart` method is called asynchronously when the resource is created, and the `.aclose` method is called asynchronously when the resource is released.

### Resource events

Sometimes, it can be useful to split the process of initializing and managing the lifecycle of an instance into separate providers.

```python
from typing import Iterator

from anydi import Container


class Client:
    def __init__(self) -> None:
        self.started = False
        self.closed = False

    def start(self) -> None:
        self.started = True

    def close(self) -> None:
        self.closed = True


container = Container()


@container.provider(scope="singleton")
def client_provider() -> Client:
    return Client()


@container.provider(scope="singleton")
def client_lifespan(client: Client) -> t.Iterator[None]:
    client.start()
    yield
    client.close()


client = container.resolve(Client)

assert not client.started
assert not client.closed

container.start()

assert client.started
assert not client.closed

container.close()

assert client.started
assert client.closed
```

!!! note

    This pattern can be used for both synchronous and asynchronous resources.


## Overriding Providers

Sometimes it's necessary to override a provider with a different implementation. To do this, you can register the provider with the override=True property set.

For example, suppose you have registered a singleton provider for a string:

```python
from anydi import Container

container = Container()


@container.provider(scope="singleton")
def hello_message() -> str:
    return "Hello, world!"


@container.provider(scope="singleton", override=True)
def goodbye_message() -> str:
    return "Goodbye!"


assert container.resolve(str) == "Goodbye!"
```

Note that if you try to register the provider without passing the override parameter as True, it will raise an error:

```python
@container.provider(scope="singleton")  # will raise an error
def goodbye_message() -> str:
    return "Good-bye!"
```


## Injecting Dependencies

In order to use the dependencies that have been provided to the `Container`, they need to be injected into the functions or classes that require them. This can be done by using the `@container.inject` decorator.

Here's an example of how to use the `@container.inject` decorator:

```python
from anydi import auto, Container


class Service:
    def __init__(self, name: str) -> None:
        self.name = name


container = Container()


@container.provider(scope="singleton")
def service() -> Service:
    return Service(name="demo")


@container.inject
def handler(service: Service = auto) -> None:
    print(f"Hello, from service `{service.name}`")
```

Note that the service argument in the handler function has been given a default value of `auto` mark. This is done so that `AnyDI` knows which dependency to inject when the handler function is called.

Once the dependencies have been injected, the function can be called as usual, like so:

```python
handler()
```

You can also call the callable object with injected dependencies using the `run` method of the `Container` instance:

```python
from anydi import auto, Container


class Service:
    def __init__(self, name: str) -> None:
        self.name = name


container = Container()


@container.provider(scope="singleton")
def service() -> Service:
    return Service(name="demo")


def handler(service: Service = auto) -> None:
    print(f"Hello, from service `{service.name}`")


container.run(handler)
```

In this case, the `run` method will automatically inject the dependencies and call the handler function. Using `@container.inject` is not necessary in this case.


### Scanning Injections

`AnyDI` provides a simple way to inject dependencies by scanning Python modules or packages.
For example, your application might have the following structure:

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
from anydi import auto, injectable

from app.services import Service


@injectable
def my_handler(service: Service = auto) -> None:
    print(f"Hello, from service `{service.name}`")
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

The scan method takes a list of directory paths as an argument and recursively searches those directories for Python modules containing `@inject`-decorated functions or classes.

### Scanning Injections by tags

You can also scan for providers or injectables in specific tags. To do so, you need to use the tags argument when registering providers or injectables. For example:

```python
from anydi import Container

container = Container()
container.scan(["app.handlers"], tags=["tag1"])
```

This will scan for `@injectable` annotated target only with defined `tags` within the `app.handlers` module.


## Modules

`AnyDI` provides a way to organize your code and configure dependencies for the dependency injection container.
A module is a class that extends the `Module` base class and contains the configuration for the container.

Here's an example how to create and register simple module:

```python
from anydi import Container, Module, provider


class Repository:
    pass


class Service:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo


class AppModule(Module):
    def configure(self, container: Container) -> None:
        container.register(Repository, lambda: Repository(), scope="singleton")

    @provider(scope="singleton")
    def service(self, repo: Repository) -> Service:
        return Service(repo=repo)


container = Container(modules=[AppModule()])

# or
# container.register_module(AppModule())

assert container.is_registered(Service)
assert container.is_registered(Repository)
```

With `AnyDI`'s Modules, you can keep your code organized and easily manage your dependencies.


## Testing

To use `AnyDI` with your testing framework, use `TestContainer` and call the `.override(interface=..., instance=...)` context manager
to temporarily replace a dependency with an overridden instance during testing. This allows you to isolate the code being tested from its dependencies.
The with `container.override()` context manager ensures that the overridden instance is used only within the context of the with block.
Once the block is exited, the original dependency is restored.

```python
from dataclasses import dataclass
from unittest import mock

from anydi import auto
from anydi.testing import TestContainer


@dataclass(kw_only=True)
class Item:
    name: str


class Repository:
    def __init__(self) -> None:
        self.items: list[Item] = []

    def all(self) -> list[Item]:
        return self.items


class Service:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def get_items(self) -> list[Item]:
        return self.repo.all()


container = TestContainer()


@container.inject
def get_items(service: Service = auto) -> list[Item]:
    return service.get_items()


def test_handler() -> None:
    repo_mock = mock.Mock(spec=Repository)
    repo_mock.all.return_value = [Item(name="mock1"), Item(name="mock2")]

    with container.override(Repository, repo_mock):
        assert get_items() == [Item(name="mock1"), Item(name="mock2")]
```

To create a `TestContainer` from the original container for testing, use the `.from_container()` method:

```python
from anydi import Container
from anydi.testing import TestContainer


def init_container(testing: bool = False) -> Container:
    container = Container()
    if testing:
        return TestContainer.from_container(container)
    return container
```

### Pytest Plugin

`AnyDI` offers a pytest plugin that simplifies the testing process. You can annotate a test function with the `@pytest.mark.inject` decorator to automatically inject dependencies into the test function, or you can set the global configuration value `anydi_inject_all` to `True` to inject dependencies into all test functions automatically.

Additionally, you need to define a `container` fixture to provide a `Container` instance for the test function, or use the `anydi_setup_container` fixture.

```python
import pytest

from anydi.testing import TestContainer


@pytest.fixture(scope="session")
def container() -> TestContainer:
    return TestContainer()


@pytest.mark.inject
def test_service_get_items(container: TestContainer, service: Service) -> None:
    repo_mock = mock.Mock(spec=Repository)
    repo_mock.all.return_value = [Item(name="mock1"), Item(name="mock2")]

    with container.override(Repository, repo_mock):
        assert service.get_items() == [Item(name="mock1"), Item(name="mock2")]
```

The message argument is injected into the test function thanks to the `@pytest.mark.inject` decorator.

PS! `Pytest` fixtures will always have higher priority than the `@pytest.mark.inject` decorator. This means that if
both a pytest fixture and the `@pytest.mark.inject` decorator attempt to provide a value for the same name, the value
from the pytest fixture will be used.

Using `.create` method you can create a new instance with overridden dependencies for testing:

```python
def test_handler() -> None:
    repo_mock = mock.Mock(spec=Repository)
    repo_mock.all.return_value = [Item(name="mock1"), Item(name="mock2")]

    service = container.create(Service, repo=repo_mock)

    assert service.get_items() == [Item(name="mock1"), Item(name="mock2")]
```

## Conclusion

Check [examples](examples/basic.md) which shows how to use `AnyDI` in real-life application.
