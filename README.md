# PyxDI (in development)

`PyxDI` is a modern, lightweight and async-friendly Python Dependency Injection library that leverages type annotations ([PEP 484](https://peps.python.org/pep-0484/))
to effortlessly manage dependencies in your applications.

[![CI](https://github.com/antonrh/pyxdi/actions/workflows/ci.yml/badge.svg)](https://github.com/antonrh/pyxdi/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/antonrh/pyxdi/branch/main/graph/badge.svg?token=67CLD19I0C)](https://codecov.io/gh/antonrh/pyxdi)
[![Documentation Status](https://readthedocs.org/projects/pyxdi/badge/?version=latest)](https://pyxdi.readthedocs.io/en/latest/?badge=latest)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---
Documentation

http://pyxdi.readthedocs.io/

---

## Requirements

Python 3.7+

and requires [anyio](https://github.com/agronholm/anyio)

## Installation

Install using `pip`:

```shell
pip install pyxdi
```

or using `poetry`:

```shell
poetry add pyxdi
```

## Quick Example

*app.py*

```python
import pyxdi

di = pyxdi.PyxDI()


@di.provider
def message() -> str:
    return "Hello, world!"


@di.inject
def say_hello(message: str = pyxdi.dep) -> None:
    print(message)


if __name__ == "__main__":
    say_hello()
```

## TODO
* Documentation (in progress)
* Examples (in progress)
