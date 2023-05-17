# Usage

## Providers

Providers are the backbone of `PyxDI`. A provider is a function or a class that returns an instance of a specific type.
Once a provider is registered with PyxDI, it can be used to resolve dependencies throughout the application.

### Registering Providers

To register a provider, you can use the `register_provider` method of the `PyxDI` instance. The method takes
three arguments: the type of the object to be provided, the provider function or class, and an optional scope.

```python
import pyxdi

di = pyxdi.PyxDI()


def message() -> str:
    return "Hello, message!"


di.register_provider(str, message, scope="singleton")

assert di.get(str) == "Hello, world!"
```

Alternatively, you can use the provider decorator to register a provider function. The decorator takes care of registering the provider with `PyxDI`.

```python
import pyxdi

di = pyxdi.PyxDI()


@di.provider
def message() -> str:
    return "Hello, message!"


assert di.get(str) == "Hello, world!"
```

### Unregistering Providers

To unregister a provider, you can use the `unregister_provider` method of the `PyxDI` instance. The method takes
interface of the dependency to be unregistered.

```python
import pyxdi

di = pyxdi.PyxDI()


@di.provider
def message() -> str:
    return "Hello, message!"


assert di.has_provider(str)

di.unregister_provider(str)

assert not di.has_provider(str)
```


## Scopes

PyxDI supports three different scopes for providers:

* `transient`
* `singleton`
* `request`

### `transient` scope

Providers with transient scope create a new instance of the object each time it's requested. You can set the scope when registering a provider.

```python
import random

import pyxdi

di = pyxdi.PyxDI()


@di.provider(scope="transient")
def message() -> str:
    return random.choice(["hello", "hola", "ciao"])


print(di.get(str))  # will print random message
```

### `singleton` scope

Providers with singleton scope create a single instance of the object and return it every time it's requested.

```python
import pyxdi

class Service:
    def __init__(self, name: str) -> None:
        self.name = name


di = pyxdi.PyxDI()



@di.provider(scope="singleton")
def service() -> Service:
    return Service(name="demo")


assert di.get(Service) == di.get(Service)
```

### `request` scope

Providers with request scope create an instance of the object for each request. The instance is only available within the context of the request.

```python
import pyxdi


class Request:
    def __init__(self, path: str) -> None:
        self.path = path


di = pyxdi.PyxDI()


@di.provider(scope="request")
def request_provider() -> Request:
    return Request(path="/")


with di.request_context():
    assert di.get(Request).path == "/"

di.get(Request)  # this will raise LookupError
```

or using asynchronous request context:

```python
import pyxdi

di = pyxdi.PyxDI()


@di.provider(scope="request")
def request_provider() -> Request:
    return Request(path="/")


async def main() -> None:
    async with di.arequest_context():
        assert di.get(Request).path == "/"
```

## Resource Providers

Resource providers are special types of providers that need to be started and stopped. PyxDI supports synchronous and asynchronous resource providers.

### Synchronous Resources

Here is an example of a synchronous resource provider that manages the lifecycle of a Resource object:

```python
import typing as t

import pyxdi


class Resource:
    def __init__(self, name: str) -> None:
        self.name = name

    def start(self) -> None:
        print("start resource")

    def close(self) -> None:
        print("close resource")


di = pyxdi.PyxDI()


@di.provider(scope="singleton")
def resource_provider() -> t.Iterator[Resource]:
    resource = Resource(name="demo")
    resource.start()
    yield resource
    resource.close()


di.start()  # start resources

assert di.get(Resource).name == "demo"

di.close()  # close resources
```

In this example, the resource_provider function returns an iterator that yields a single Resource object. The `.start` method is called when the resource is created, and the `.close` method is called when the resource is released.

### Asynchronous Resources

Here is an example of an asynchronous resource provider that manages the lifecycle of an asynchronous Resource object:

```python
import asyncio
import typing as t

import pyxdi


class Resource:
    def __init__(self, name: str) -> None:
        self.name = name

    async def start(self) -> None:
        print("start resource")

    async def close(self) -> None:
        print("close resource")


di = pyxdi.PyxDI()


@di.provider(scope="singleton")
async def resource_provider() -> t.AsyncIterator[Resource]:
    resource = Resource(name="demo")
    await resource.start()
    yield resource
    await resource.close()


async def main() -> None:
    await di.astart()  # start resources

    assert di.get(Resource).name == "demo"

    await di.aclose()  # close resources


asyncio.run(main())
```

In this example, the `resource_provider` function returns an asynchronous iterator that yields a single Resource object. The `.astart` method is called asynchronously when the resource is created, and the `.aclose` method is called asynchronously when the resource is released.

### Resource events

Sometimes, it can be useful to split the process of initializing and managing the lifecycle of an instance into separate providers.

```python
import typing as t

import pyxdi


class Client:
    def __init__(self) -> None:
        self.started = False
        self.closed = False

    def start(self) -> None:
        self.started = True

    def close(self) -> None:
        self.closed = True


di = pyxdi.PyxDI()


@di.provider
def client_provider() -> Client:
    return Client()


@di.provider
def client_lifespan(client: Client) -> t.Iterator[None]:
    client.start()
    yield
    client.close()


client = di.get(Client)

assert not client.started
assert not client.closed

di.start()

assert client.started
assert not client.closed


di.close()

assert client.started
assert client.closed
```

!!! note

    This pattern can be used for both synchronous and asynchronous resources.


## Default Scope

By default, providers are registered with a `singleton` scope. You can change the default scope by passing the default_scope parameter to the `PyxDI` constructor. This way, you don't have to specify the scope for each provider.

```python
import pyxdi

di = pyxdi.PyxDI(default_scope="transient")


@di.provider    # will use `default_scope`
def message_provider() -> str:
    return "Hello, message!"


assert di.get(str) == "Hello, world!"
```

In this example, the message_provider function is registered as a singleton provider because default_scope is set to `singleton`.

## Singleton Provider

You can register a provider as a singleton by calling the singleton method on the `PyxDI` instance.

```python
import pyxdi

di = pyxdi.PyxDI()
di.singleton(str, "Hello, world!")

assert di.get(str) == "Hello, world!"
```

## Overriding Providers

Sometimes it's necessary to override a provider with a different implementation. To do this, you can call the singleton() or register_provider() method again with the same key.

For example, suppose you have registered a singleton provider for a string:

```python
import pyxdi

di = pyxdi.PyxDI()
di.singleton(str, "Hello, world!")
```

If you later want to change the value of the string to "Good-bye", you can call the singleton() method again with the same key:

```python
di.singleton(str, "Good-bye", override=True)
```

Note that if you call singleton() without passing the override parameter as True, it will raise an error. Also, once you override a provider, any further requests for that key will return the new implementation.

```python
di.singleton(str, "Good-bye")  # will raise an error
```

## Auto-Register Providers

In addition to registering providers manually, you can enable the auto_register feature of the DI container to automatically register providers for classes that have type hints in their constructor parameters.

For example, suppose you have a class that depends on another class:

```python
import typing as t


class Database:
    def execute(self, *args: t.Any) -> t.Any:
        return args

    def connect(self) -> None:
        print("connected")

    def disconnect(self) -> None:
        print("disconnected")


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get(self, ident: str) -> t.Any:
        return self.db.execute(ident)


class Service:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def get(self, ident: str) -> t.Any:
        return self.repo.get(ident=ident)
```

If you create a `PyxDI` instance with `auto_register=True`, it will automatically register a provider for `Service` and `Repository` with provided `Database`:

```python
import pyxdi

di = pyxdi.PyxDI(auto_register=True)


@di.provider
def db() -> t.Iterator[Database]:
    db = Database()
    db.connect()
    yield db
    db.disconnect()


di.start()

service = di.get(Service)

assert service.get(ident="abc") == ("abc",)

di.close()
```

## Injecting Dependencies

In order to use the dependencies that have been provided to the `PyxDI` container, they need to be injected into the functions or classes that require them. This can be done by using the @di.inject decorator.

Here's an example of how to use the `@di.inject` decorator:

```python
import pyxdi


class Service:
    def __init__(self, name: str) -> None:
        self.name = name


di = pyxdi.PyxDI()


@di.provider
def service() -> Service:
    return Service(name="demo")


@di.inject
def handler(service: Service = pyxdi.dep) -> None:
    print(f"Hello, from service `{service.name}`")
```

Note that the service argument in the handler function has been given a default value of pyxdi.dep. This is done so that `PyxDI` knows which dependency to inject when the handler function is called.

Once the dependencies have been injected, the function can be called as usual, like so:

```python
handler()
```

### Lazy Injections

Lazy injections allows you to defer the creation of an object until it is actually required, instead of creating it
immediately at the start of the application. This can lead to better application performance by minimizing the number
of unnecessary object creations, resulting in reduced memory consumption.

Here's an example of how to use the `@di.inject(lazy=True)` decorator:

```python
import typing as t
from collections.abc import Iterable

import pyxdi


class Database:
    def connect(self) -> None:
        ...

    def disconnect(self) -> None:
        ...

    def execute(self, query: str, **params: t.Any) -> t.Any:
        ...


di = pyxdi.PyxDI()


@di.provider
def db() -> Iterable[Database]:
    db = Database()
    db.connect()
    yield db
    db.disconnect()


@di.inject(lazy=True)
def handler(object_id: t.Optional[int], db: Database = pyxdi.dep) -> None:
    if not object_id:
        raise Exception("Object id cannot be empty.")
    db.execute("SELECT name FROM object WHERE id = :id", id=object_id)


handler(object_id=None)
```

In this example, the `Database` object is only instantiated and connected when the `db` parameter is actually used in the handler function.

By using `lazy=True`, you can avoid unnecessary object creation and improve the performance of your application.


### Scanning Injection

`PyxDI` provides a simple way to inject dependencies by scanning Python modules or packages.
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
import pyxdi

from app.services import Service


@pyxdi.inject
def my_handler(service: Service = pyxdi.dep) -> None:
    print(f"Hello, from service `{service.name}`")
```

`main.py` starts the DI container and scans the app `handlers.py` module:

```python
from app.services import Service

import pyxdi

di = pyxdi.PyxDI()


@di.provider
def service() -> str:
    return Service(name="demo")


di.scan(["app.handlers"])
di.start()

# application context

di.close()
```

The scan method takes a list of directory paths as an argument and recursively searches those directories for Python modules containing `@pyxdi.inject`-decorated functions or classes.

### Scanning Injection by tags

You can also scan for providers or injectables in specific tags. To do so, you need to use the tags argument when registering providers or injectables. For example:

```python
import pyxdi

di = pyxdi.PyxDI()
di.scan(["app.handlers"], tags=["tag1"])
```

This will scan for `@inject` annotated target only with defined `tags` within the `app.handlers` module.


## Modules

`PyxDI` provides a way to organize your code and configure dependencies for the dependency injection container.
A module is a class that extends the `pyxdi.Module` base class and contains the configuration for the container.

Here's an example how to create and register simple module:

```python
import pyxdi


class Repository:
    pass


class Service:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo


class AppModule(pyxdi.Module):
    def configure(self, di: pyxdi.PyxDI) -> None:
        di.singleton(Repository, Repository())

    @pyxdi.provider(scope="singleton")
    def configure_service(self, repo: Repository) -> Service:
        return Service(repo=repo)


di = pyxdi.PyxDI(modules=[AppModule()])

# or
# di.register_module(AppModule())

assert di.has_provider(Service)
assert di.has_provider(Repository)
```

!!! note

    If the provider has already been registered, it will be overridden.


With `PyxDI`'s application Modules, you can keep your code organized and easily manage your dependencies.


## Testing

To use `PyxDI` with your testing framework, you can use the `override` context manager to temporarily replace a dependency with an overridden instance
during testing. This allows you to isolate the code being tested from its dependencies. The with `di.override()` context manager is used to ensure that
the overridden instance is used only within the context of the with block. Once the block is exited, the original dependency is restored.

```python
from unittest import mock

import pyxdi


class Service:
    def __init__(self, name: str) -> None:
        self.name = name

    def say_hello(self) -> str:
        return f"Hello, from `{self.name}` service!"


di = pyxdi.PyxDI()


@di.provider
def service() -> Service:
    return Service(name="demo")


@di.inject
def hello_handler(service: Service = pyxdi.dep) -> str:
    return service.say_hello()


def test_hello_handler() -> None:
    service_mock = mock.Mock(spec=Service)
    service_mock.say_hello.return_value = "Hello, from service mock!"

    with di.override(Service, service_mock):
        assert hello_handler() == "Hello, from service mock!"
```

## Conclusion

Check [examples](examples/basic.md) which shows how to use `PyxDI` in real-life application.
