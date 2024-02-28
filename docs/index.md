# AnyDI

`AnyDI` is a lightweight Python Dependency Injection library that supports any synchronous or asynchronous code through type annotations ([PEP 484](https://peps.python.org/pep-0484/)).

[![CI](https://github.com/antonrh/anydi/actions/workflows/ci.yml/badge.svg)](https://github.com/antonrh/anydi/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/antonrh/anydi/branch/main/graph/badge.svg?token=67CLD19I0C)](https://codecov.io/gh/antonrh/anydi)
[![Documentation Status](https://readthedocs.org/projects/anydi/badge/?version=latest)](https://anydi.readthedocs.io/en/latest/?badge=latest)

---

## Requirements

Python 3.8+

and optional dependencies:

* [anyio](https://github.com/agronholm/anyio) (for supporting synchronous resources with an asynchronous runtime)


## Installation

Install using `pip`:

```shell
pip install anydi
```

or using `poetry`:

```shell
poetry add anydi
```

## Quick Example

*app.py*

```python
from anydi import auto, Container

container = Container()


@container.provider(scope="singleton")
def message() -> str:
    return "Hello, world!"


@container.inject
def say_hello(message: str = auto()) -> None:
    print(message)


if __name__ == "__main__":
    say_hello()
```
