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
