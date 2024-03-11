# AnyDI

<p align="center">
    <i>Modern, lightweight Dependency Injection library using type annotations.</i>
</p>

<p align="center">
    <a href="https://github.com/antonrh/anydi/actions/workflows/ci.yml" target="_blank">
        <img src="https://github.com/antonrh/anydi/actions/workflows/ci.yml/badge.svg" alt="CI">
    </a>
    <a href="https://codecov.io/gh/antonrh/anydi" target="_blank">
        <img src="https://codecov.io/gh/antonrh/anydi/branch/main/graph/badge.svg?token=67CLD19I0C" alt="Coverage">
    </a>
    <a href="https://anydi.readthedocs.io/en/latest/?badge=latest" target="_blank">
        <img src="https://readthedocs.org/projects/anydi/badge/?version=latest" alt="Documentation">
    </a>
</p>

---
Documentation

http://anydi.readthedocs.io/

---

`AnyDI` is a modern, lightweight Dependency Injection library suitable for any synchronous or asynchronous applications with Python 3.8+, based on type annotations ([PEP 484](https://peps.python.org/pep-0484/)).

The key features are:

* **Type-safe**: Resolves dependencies using type annotations.
* **Async Support**: Compatible with both synchronous and asynchronous providers and injections.
* **Scoping**: Supports singleton, transient, and request scopes.
* **Easy to Use**: Designed for simplicity and minimal boilerplate.
* **Named Dependencies**: Supports named dependencies using `Annotated` type.
* **Resource Management**: Manages resources using context managers.
* **Modular: Facilitates** a modular design with support for multiple modules.
* **Scanning**: Automatically scans for injectable functions and classes.
* **Integrations**: Provides easy integration with popular frameworks and libraries.
* **Testing**: Simplifies testing by allowing provider overrides.

## Installation

```shell
pip install anydi
```

## Quick Example

*app.py*

```python
from anydi import Container, dep

container = Container()


@container.provider(scope="singleton")
def message() -> str:
    return "Hello, world!"


@container.inject
def say_hello(message: str = dep()) -> None:
    print(message)


if __name__ == "__main__":
    say_hello()
```

## FastAPI Example

*app.py*

```python
from fastapi import FastAPI

import anydi.ext.fastapi
from anydi import Container
from anydi.ext.fastapi import Inject

container = Container()


@container.provider(scope="singleton")
def message() -> str:
    return "Hello, World!"


app = FastAPI()


@app.get("/hello")
def say_hello(message: str = Inject()) -> dict[str, str]:
    return {"message": message}


# Install the container into the FastAPI app
anydi.ext.fastapi.install(app, container)
```
