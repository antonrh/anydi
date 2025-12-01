# Modules

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
        container.register(Repository)

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

