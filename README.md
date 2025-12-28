# AnyDI

<div style="text-align: center;">

Modern, lightweight Dependency Injection library using type annotations.

[![CI](https://github.com/antonrh/anydi/actions/workflows/ci.yml/badge.svg)](https://github.com/antonrh/anydi/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/antonrh/anydi/branch/main/graph/badge.svg)](https://codecov.io/gh/antonrh/anydi)
[![Documentation](https://readthedocs.org/projects/anydi/badge/?version=latest)](https://anydi.readthedocs.io/en/latest/)
[![CodSpeed](https://img.shields.io/endpoint?url=https://codspeed.io/badge.json)](https://codspeed.io/antonrh/anydi?utm_source=badge)

</div>

---
Documentation

http://anydi.readthedocs.io/

---

`AnyDI` is a modern, lightweight Dependency Injection library suitable for any synchronous or asynchronous applications with Python 3.10+, based on type annotations ([PEP 484](https://peps.python.org/pep-0484/)).

The key features are:

* **Type-safe**: Dependency resolution is driven by type hints.
* **Async-ready**: Works the same for sync and async providers or injections.
* **Scoped**: Built-in singleton, transient, and request scopes, plus custom scopes.
* **Simple**: Small surface area keeps boilerplate low.
* **Fast**: Has minimal overhead and resolves dependencies quickly.
* **Named**: `Annotated[...]` makes multiple bindings per type simple.
* **Managed**: Providers can open/close resources via context managers.
* **Modular**: Compose containers or modules for large apps.
* **Scanning**: Auto-discovers injectable callables.
* **Integrated**: Extensions for popular frameworks.
* **Testable**: Override providers directly in tests.

## Installation

```shell
pip install anydi
```

## Quick Example

### Define a Service (`app/services.py`)

```python
class GreetingService:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"
```

### Create the Container and Providers (`app/container.py`)

```python
from anydi import Container

from app.services import GreetingService


container = Container()


@container.provider(scope="singleton")
def service() -> GreetingService:
    return GreetingService()
```

### Resolve Dependencies Directly

```python
from app.container import container
from app.services import GreetingService


service = container.resolve(GreetingService)

if __name__ == "__main__":
    print(service.greet("World"))
```

### Inject Into Functions (`app/main.py`)

```python
from anydi import Provide

from app.container import container
from app.services import GreetingService


def greet(service: Provide[GreetingService]) -> str:
    return service.greet("World")


if __name__ == "__main__":
    print(container.run(greet))
```

### Test with Overrides (`tests/test_app.py`)

```python
from unittest import mock

from app.container import container
from app.services import GreetingService
from app.main import greet


def test_greet() -> None:
    service_mock = mock.Mock(spec=GreetingService)
    service_mock.greet.return_value = "Mocked"

    with container.override(GreetingService, service_mock):
        result = container.run(greet)

    assert result == "Mocked"
```

### Integrate with FastAPI (`app/api.py`)

```python
from typing import Annotated

import anydi.ext.fastapi
from fastapi import FastAPI

from anydi import Provide
from app.container import container
from app.services import GreetingService


app = FastAPI()


@app.get("/greeting")
async def greet(
    service: Provide[GreetingService]
) -> dict[str, str]:
    return {"greeting": service.greet("World")}


anydi.ext.fastapi.install(app, container)
```

### Test the FastAPI Integration (`test_api.py`)

```python
from unittest import mock

from fastapi.testclient import TestClient

from app.api import app
from app.container import container
from app.services import GreetingService


client = TestClient(app)


def test_api_greeting() -> None:
    service_mock = mock.Mock(spec=GreetingService)
    service_mock.greet.return_value = "Mocked"

    with container.override(GreetingService, service_mock):
        response = client.get("/greeting")

    assert response.json() == {"greeting": "Mocked"}
```

### Integrate with Django Ninja

Install the Django integration extras:

```sh
pip install 'anydi-django[ninja]'
```

Expose the container factory (`app/container.py`):

```python
from anydi import Container

from app.services import GreetingService


container = Container()


@container.provider(scope="singleton")
def service() -> GreetingService:
    return GreetingService()
```

Configure Django (`settings.py`):

```python
INSTALLED_APPS = [
    ...,
    "anydi_django",
]

ANYDI = {
    "CONTAINER_FACTORY": "app.container.container",
    "PATCH_NINJA": True,
}
```

Wire Django Ninja (`urls.py`):

```python
from typing import Annotated, Any

from anydi import Provide
from django.http import HttpRequest
from django.urls import path
from ninja import NinjaAPI

from app.services import GreetingService


api = NinjaAPI()


@api.get("/greeting")
def greet(request: HttpRequest, service: Provide[GreetingService]) -> Any:
    return {"greeting": service.greet("World")}


urlpatterns = [
    path("api/", api.urls),
]
```

## What's Next?

Ready to learn more? Check out these resources:

**Core Documentation:**
- [Core Concepts](https://anydi.readthedocs.io/en/latest/concepts/) - Understand containers, providers, scopes, and dependency injection
- [Providers](https://anydi.readthedocs.io/en/latest/usage/providers/) - Learn about registration, named providers, and resource management
- [Scopes](https://anydi.readthedocs.io/en/latest/usage/scopes/) - Master lifecycle management with built-in and custom scopes
- [Dependency Injection](https://anydi.readthedocs.io/en/latest/usage/injection/) - Explore injection patterns and techniques
- [Testing](https://anydi.readthedocs.io/en/latest/usage/testing/) - Write testable code with provider overrides

**Framework Integrations:**
- [FastAPI](https://anydi.readthedocs.io/en/latest/extensions/fastapi/) - Build modern APIs with automatic dependency injection
- [Django](https://anydi.readthedocs.io/en/latest/extensions/django/) - Integrate with Django and Django Ninja
- [FastStream](https://anydi.readthedocs.io/en/latest/extensions/faststream/) - Message broker applications
- [Typer](https://anydi.readthedocs.io/en/latest/extensions/typer/) - CLI applications with async support
- [Pydantic Settings](https://anydi.readthedocs.io/en/latest/extensions/pydantic_settings/) - Configuration management

**Full Documentation:**
- [Read the Docs](https://anydi.readthedocs.io/) - Complete documentation with examples and guides
