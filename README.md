# Pyxdi

`Pyxdi` is a modern and lightweight Python Dependency Injection library that leverages type annotations
to effortlessly manage dependencies in your applications, inspired by the functionality of `pytest` fixtures."

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
def say_hello(message: str = pyxdi.mark) -> None:
    print(message)


if __name__ == "__main__":
    say_hello()
```
