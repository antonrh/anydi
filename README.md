# InitDI

> [!IMPORTANT]
> `initdi` previously known as `pyxdi` has been renamed to `initdi` and is now available on PyPI.
> Please `initdi` package instead of `pyxdi` for the latest version and updates.


`InitDI` is a modern, lightweight and async-friendly Python Dependency Injection library that leverages type annotations ([PEP 484](https://peps.python.org/pep-0484/))
to effortlessly manage dependencies in your applications.

[![CI](https://github.com/antonrh/initdi/actions/workflows/ci.yml/badge.svg)](https://github.com/antonrh/initdi/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/antonrh/initdi/branch/main/graph/badge.svg?token=67CLD19I0C)](https://codecov.io/gh/antonrh/initdi)
[![Documentation Status](https://readthedocs.org/projects/initdi/badge/?version=latest)](https://initdi.readthedocs.io/en/latest/?badge=latest)

---
Documentation

http://initdi.readthedocs.io/

---

## Requirements

Python 3.8+

and optional dependencies:

* [anyio](https://github.com/agronholm/anyio) (for supporting synchronous resources with an asynchronous runtime)


## Installation

Install using `pip`:

```shell
pip install initdi
```

or using `poetry`:

```shell
poetry add initdi
```

## Quick Example

*app.py*

```python
from initdi import dep, InitDI

di = InitDI()


@di.provider(scope="singleton")
def message() -> str:
    return "Hello, world!"


@di.inject
def say_hello(message: str = dep) -> None:
    print(message)


if __name__ == "__main__":
    say_hello()
```
