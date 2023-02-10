# Pyxdi

`Pyxdi` is a modern and lightweight Dependency Injection Python library.
Inspired by `pytest` fixtures, which provides an easy and intuitive way to manage dependencies in your Python application.

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## Installing

Install using `pip`:

```bash
pip install pyxdi
```

## Quick Example

*app.py*

```python
import pyxdi

pyxdi.init()


@pyxdi.dep
def message() -> str:
    return "Hello, world!"


@pyxdi.inject
def say_hello(message: str = pyxdi.depends()) -> None:
    print(message)


if __name__ == "__main__":
    say_hello()
```
