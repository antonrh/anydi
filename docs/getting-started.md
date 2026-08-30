# Getting started

This page builds one small application: a service with a dependency of its
own, a container that knows how to create both, and a function that receives
the service without asking for it.

## Install

```console
$ pip install anydi
```

## Define the classes

Nothing here knows about `AnyDI`. `Greeter` takes a `Config`, and that is the
only thing that says one depends on the other.

```python
class Config:
    def __init__(self, greeting: str) -> None:
        self.greeting = greeting


class Greeter:
    def __init__(self, config: Config) -> None:
        self.config = config

    def greet(self, name: str) -> str:
        return f"{self.config.greeting}, {name}"
```

## Register the providers

A provider is a function that returns an instance. Its return annotation says
what it provides, and its parameters say what it needs, so the container can
work out the order.

```python
from anydi import Container

container = Container()


@container.provider(scope="singleton")
def config() -> Config:
    return Config(greeting="Hello")


@container.provider(scope="singleton")
def greeter(config: Config) -> Greeter:
    return Greeter(config)
```

The `singleton` scope means one instance for the life of the container. The
other scopes are on the [Scopes](usage/scopes.md) page.

## Resolve

`resolve` creates the `Config` first, hands it to `greeter`, and keeps both.
Asking again returns the same instance.

```python
greeter_instance = container.resolve(Greeter)

print(greeter_instance.greet("Ada"))  # Hello, Ada
print(container.resolve(Greeter) is greeter_instance)  # True
```

## Inject

Resolving by hand is fine at the edge of an application. Everywhere else, let
the container fill the parameter. `Provide` marks which parameter to fill, and
`run` calls the function with it.

```python
from anydi import Provide


def welcome(name: str, greeter: Provide[Greeter]) -> str:
    return greeter.greet(name)


print(container.run(welcome, "Grace"))  # Hello, Grace
```

The other ways to inject, including the `@container.inject` decorator and the
framework extensions, are on the
[Dependency Injection](usage/injection.md) page.

## Clean up after a dependency

A provider that yields instead of returning is a resource: the code after
`yield` runs when the container closes.

```python
from collections.abc import Iterator


@container.provider(scope="singleton")
def connection() -> Iterator[str]:
    print("connection opened")
    yield "connection"
    print("connection closed")


container.resolve(str)
container.close()
```

Use `await container.aclose()` when any of the resources is asynchronous.

## What to read next

- [Core Concepts](concepts.md) for containers, providers, scopes and injection
  as a whole.
- [Scopes](usage/scopes.md) if you need a dependency per request rather than
  per application.
- [Testing](usage/testing.md) for overriding a provider in a test.
- [Reference](reference.md) for everything `Container` offers.
