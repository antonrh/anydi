# Injection

In order to use the dependencies that have been provided to the `Container`, they need to be injected into the functions or classes that require them. This can be done by using the `@container.inject` decorator.

Here's an example of how to use the `@container.inject` decorator:

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
```

Note that the service argument in the handler function has been given a default value of the `Inject()` marker. This lets `AnyDI` know which dependency to inject when the handler function is called.

Once the dependencies have been injected, the function can be called as usual, like so:

```python
handler()
```

You can also call the callable object with injected dependencies using the `run` method of the `Container` instance:

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

In this case, the `run` method will automatically inject the dependencies and call the handler function. Using `@container.inject` is not necessary in this case.

## Annotation Equivalents

AnyDI recognizes the following forms as equivalent ways to declare an injected dependency:

```python
dependency: MyType = Inject()
dependency: Annotated[MyType, Inject()]
dependency: Provide[MyType]
```

Choose whichever aligns with the framework or style you are using; they all resolve to the same provider lookup.


## Scanning Injections

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
from anydi import Inject, injectable

from app.services import Service


@injectable
def my_handler(service: Service = Inject()) -> None:
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

## Scanning Injections by tags

You can also scan for providers or injectables in specific tags. To do so, you need to use the tags argument when registering providers or injectables. For example:

```python
from anydi import Container

container = Container()
container.scan(["app.handlers"], tags=["tag1"])
```

This will scan for `@injectable` annotated target only with defined `tags` within the `app.handlers` module.
