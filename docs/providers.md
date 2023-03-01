# Providers

Providers are the backbone of PyxDI. A provider is a function or a class that returns an instance of a specific type.
Once a provider is registered with PyxDI, it can be used to resolve dependencies throughout the application.

## Registering providers

To register a provider, you can use the register_provider method of the PyxDI instance. The method takes
three arguments: the type of the object to be provided, the provider function or class, and an optional scope.

```python
import pyxdi

di = pyxdi.PyxDI()


def message() -> str:
    return "Hello, message!"


di.register_provider(str, message, scope="singleton")

assert di.get(str) == "Hello, world!"
```

Alternatively, you can use the provider decorator to register a provider function. The decorator takes care of registering the provider with PyxDI.

```python
import pyxdi

di = pyxdi.PyxDI()


@di.provider
def message() -> str:
    return "Hello, message!"


assert di.get(str) == "Hello, world!"
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

## Resource providers

Resource providers are special types of providers that need to be started and stopped. PyxDI supports synchronous and asynchronous resource providers.

### Synchronous provider

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


di.start()  # start resource

assert di.get(Resource).name == "demo"

di.close()  # close resource
```

In this example, the resource_provider function returns an iterator that yields a single Resource object. The start method is called when the resource is created, and the close method is called when the resource is released.

### Asynchronous provider

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
    await di.astart()  # start resource

    assert di.get(Resource).name == "demo"

    await di.aclose()  # close resource


asyncio.run(main())
```

In this example, the resource_provider function returns an asynchronous iterator that yields a single Resource object. The start method is called asynchronously when the resource is created, and the close method is called asynchronously when the resource is released.

## Default scope

By default, providers are registered with a `singleton` scope. You can change the default scope by passing the default_scope parameter to the PyxDI constructor. This way, you don't have to specify the scope for each provider.

```python
import pyxdi

di = pyxdi.PyxDI(default_scope="transient")


@di.provider    # will use `default_scope`
def message_provider() -> str:
    return "Hello, message!"


assert di.get(str) == "Hello, world!"
```

In this example, the message_provider function is registered as a singleton provider because default_scope is set to `singleton`.

## Singleton provider

You can register a provider as a singleton by calling the singleton method on the PyxDI instance.

```python
import pyxdi

di = pyxdi.PyxDI()
di.singleton(str, "Hello, world!")

assert di.get(str) == "Hello, world!"
```

## Overriding provider

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

## Auto-Register providers

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

If you create a PyxDI instance with auto_register=True, it will automatically register a provider for `Service` and `Repository` with provided `Database`:

```python
import pyxdi

di = pyxdi.PyxDI(auto_register=True)


@di.provider
def db_provider() -> t.Iterator[Database]:
    db = Database()
    db.connect()
    yield db
    db.disconnect()


di.start()

service = di.get(Service)

assert service.get(ident="abc") == ("abc",)

di.close()
```


## Conclusion

Check [examples](examples/basic.md) which shows how to use PyxDI in real-life application.
