# Modules

`AnyDI` lets you organize your code with modules. A module is a class that extends the `Module` base class. It contains configuration for the container.

Here is how to create and register a simple module:

```python
from anydi import Container, Module, provider


class Service:
    def __init__(self, name: str) -> None:
        self.name = name


class AppModule(Module):
    @provider(scope="singleton")
    def service(self) -> Service:
        return Service(name="demo")


container = Container(modules=[AppModule()])

# or
# container.register_module(AppModule())

assert container.is_registered(Service)
```

You can also override the `configure(self, container: Container) -> None` method to customize dependency registration when the module is loaded. Use it when you need to:

- Register dependencies programmatically
- Configure container settings
- Perform complex registration logic that can't be done with `@provider` decorators

Here is an example with `configure`:

```python
from anydi import Container, Module, provider


class Repository:
    pass


class Service:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo


class AppModule(Module):
    def configure(self, container: Container) -> None:
        container.register(Repository)

    @provider(scope="singleton")
    def service(self, repo: Repository) -> Service:
        return Service(repo=repo)


container = Container(modules=[AppModule()])

assert container.is_registered(Service)
assert container.is_registered(Repository)
```

Modules help you keep your code organized and manage dependencies easier.

