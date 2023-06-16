# Usage

## Providers

Providers are the backbone of `PyxDI`. A provider is a function or a class that returns an instance of a specific type.
Once a provider is registered with PyxDI, it can be used to resolve dependencies throughout the application.

### Registering Providers

To register a provider, you can use the `register_provider` method of the `PyxDI` instance. The method takes
three arguments: the type of the object to be provided, the provider function or class, and an scope.

```python
import pyxdi

di = pyxdi.PyxDI()


def message() -> str:
    return "Hello, message!"


di.register_provider(str, message, scope="singleton")

assert di.get_instance(str) == "Hello, world!"
```

Alternatively, you can use the provider decorator to register a provider function. The decorator takes care of registering the provider with `PyxDI`.

```python
import pyxdi

di = pyxdi.PyxDI()


@di.provider(scope="singleton")
def message() -> str:
    return "Hello, message!"


assert di.get_instance(str) == "Hello, world!"
```

### Unregistering Providers

To unregister a provider, you can use the `unregister_provider` method of the `PyxDI` instance. The method takes
interface of the dependency to be unregistered.

```python
import pyxdi

di = pyxdi.PyxDI()


@di.provider(scope="singleton")
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


print(di.get_instance(str))  # will print random message
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


assert di.get_instance(Service) == di.get_instance(Service)
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
    assert di.get_instance(Request).path == "/"

di.get_instance(Request)  # this will raise LookupError
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
        assert di.get_instance(Request).path == "/"
```

## Resource Providers

Resource providers are special types of providers that need to be started and stopped. `PyxDI` supports synchronous and asynchronous resource providers.

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

assert di.get_instance(Resource).name == "demo"

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

    assert di.get_instance(Resource).name == "demo"

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


@di.provider(scope="singleton")
def client_provider() -> Client:
    return Client()


@di.provider(scope="singleton")
def client_lifespan(client: Client) -> t.Iterator[None]:
    client.start()
    yield
    client.close()


client = di.get_instance(Client)

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


## Overriding Providers

Sometimes it's necessary to override a provider with a different implementation. To do this, you can register the provider with the override=True property set.

For example, suppose you have registered a singleton provider for a string:

```python
import pyxdi

di = pyxdi.PyxDI()


@di.provider(scope="singleton")
def hello_message() -> str:
    return "Hello, world!"


@di.provider(scope="singleton", override=True)
def goodbye_message() -> str:
    return "Goodbye!"


assert di.get_instance(str) == "Goodbye!"
```

Note that if you try to register the provider without passing the override parameter as True, it will raise an error:

```python
@di.provider(scope="singleton")  # will raise an error
def goodbye_message() -> str:
    return "Good-bye!"
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


@di.provider(scope="singleton")
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

### Scanning Injections

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


@di.provider(scope="singleton")
def service() -> str:
    return Service(name="demo")


di.scan(["app.handlers"])
di.start()

# application context

di.close()
```

The scan method takes a list of directory paths as an argument and recursively searches those directories for Python modules containing `@pyxdi.inject`-decorated functions or classes.

### Scanning Injections by tags

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
        di.register_provider(Repository, lambda: Repository(), scope="singleton")

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


@di.provider(scope="singleton")
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
