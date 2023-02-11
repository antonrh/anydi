# Pyxdi (in dev)

`Pyxdi` is a modern, lightweight and async-friendly Python Dependency Injection library that leverages type annotations ([PEP 484](https://peps.python.org/pep-0484/))
to effortlessly manage dependencies in your applications, inspired by the functionality of [pytest fixtures](https://docs.pytest.org/en/7.2.x/explanation/fixtures.html).

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

---

## TODO
* Unit tests
* Autowiring
* Documentation
* Examples
* Pypi package
* GitHub actions
