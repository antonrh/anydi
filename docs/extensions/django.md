# Django Extension

## Quick Start

Install `anydi` with `Django` support:

```sh
pip install 'anydi-django'
```

Add `anydi_django` to the **bottom** of your `INSTALLED_APPS` setting in your `Django` settings file:

```python
INSTALLED_APPS = [
    # ...
    "anydi_django",
]
```

Add `AnyDI` settings to your `Django` settings file:

```python
ANYDI = {
    "INJECT_URLCONF": "path.to.your.urls",
}
```

This configuration will inject dependencies into your Django views located in the specified URL configuration (URLconf).

Assume you have a service class that you want to inject into your views:

```python
class HelloService:
    def get_message(self) -> str:
        return "Hello, World!"
```

You can now use this service in your views as follows:

```python
import anydi
from django.http import HttpRequest, HttpResponse


def hello(request, hello_service: HelloService = anydi.auto) -> HttpResponse:
    return HttpResponse(hello_service.get_message())
```

In your `urls.py`, set up the routing:

```python
from django.urls import path

from .views import hello

urlpatterns = [
    path("hello", hello),
]
```

The `HelloService` will be automatically injected into the hello view through the provided marker `anydi.auto`.

## Settings

`ANYDI` supports the following settings:

* `CONTAINER_FACTORY: str | None` (default: `None`) - Specifies the factory function used to create the container. If not provided, the default container factory will be utilized.
* `REGISTER_SETTINGS: bool` (default: `False`) - If `True`, the container will register the Django settings within it.
* `REGISTER_COMPONENTS: bool` (default: `False`) - If `True`, the container will register Django components such as the database and cache.
* `INJECT_URLCONF: str | Sequence[str] | None` (default: `None`) - Specifies the URL configuration where dependencies should be injected.
* `MODULES: Sequence[str]` (default: `[]`) - Lists the modules to be scanned for dependencies.
* `SCAN_PACKAGES: Sequence[str]` (default: `[]`) - Designates the packages to be scanned for dependencies.
* `PATCH_NINJA: bool` (default: `False`) - If `True`, the container will modify the `ninja` framework to support dependency injection.

## Modules

To add modules to the container, you can use the `MODULES` setting:

```python
ANYDI = {
    "MODULES": [
        "yourproject.user.UserModule",
        "yourproject.payment.PaymentModule",
    ],
}
```

Assume you have a module that provides a `UserService` class:

```python
from anydi import provider

from yourproject.user.service import UserService


class UserModule:
    @provider(scope="singleton")
    def user_service(self) -> UserService:
        return UserService()
```

You can now use the UserService in your views as demonstrated in the Quick Start section.


## Custom Container

To use a custom container, you can specify the `CONTAINER_FACTORY` setting:

```python
ANYDI = {
    "CONTAINER_FACTORY": "yourproject.config.container.get_container",
}
```

In `yourproject/config/container.py`:

```python
from anydi import Container


def get_container() -> Container:
    container = Container()
    # Add custom container configuration here
    return container
```

## Request Scope

To use `request`-scoped dependencies in your Django application with `AnyDI`, include the `request_scoped_middleware`.
This middleware creates request-specific dependency instances at the start of each request, which remain available for the request’s duration.

Add the middleware to your `settings.py`:

```python
MIDDLEWARE = [
    "anydi_django.middleware.request_scoped_middleware",
    ...
]
```

With this setup, you can define and utilize `request`-scoped dependencies throughout your application.
Additionally, `HttpRequest` dependencies are automatically available in request-scoped providers,
allowing convenient access to the request object and its data in these dependencies.

## Testing

When writing tests for your Django application, you may need to mock or override services to isolate the code under test. `AnyDI` provides two approaches for mocking dependencies in your tests.

### Using `container.override`

You can use `container.override` as a context manager to temporarily replace a service with a mock. This approach is useful for functional tests where you want to override dependencies for specific test scenarios.

```python
from unittest import mock

from anydi_django import container
from django.test import Client

from your_module import HelloService


def test_hello_view() -> None:
    # Create a mock of the HelloService
    hello_service_mock = mock.MagicMock(spec=HelloService)
    hello_service_mock.get_message.return_value = "Hello from mock!"

    # Override the service in the container
    with container.override(HelloService, instance=hello_service_mock):
        client: Client = Client()
        response = client.get("/hello")

    assert response.status_code == 200
    assert b"Hello from mock!" in response.content
    hello_service_mock.get_message.assert_called_once()
```

### Using the `container` fixture with pytest

If you're using pytest, you can use the `container` fixture provided by the `anydi` pytest plugin. This approach is more convenient for test isolation and allows you to override dependencies for the entire test function or test class.

First, install `pytest-django`:

```sh
pip install pytest-django
```

Then ensure the `anydi` pytest plugin is enabled (it's automatically enabled if `anydi` is installed).

```python
from typing import Iterator
from unittest import mock

import pytest
from django.test import Client

from anydi import Container
from your_module import HelloService


@pytest.fixture
def hello_service_mock() -> mock.MagicMock:
    """Fixture that provides a mocked HelloService."""
    return mock.MagicMock(spec=HelloService, get_message=mock.Mock(return_value="Hello from pytest mock!"))


def test_hello_view_with_fixture(container: Container, hello_service_mock: mock.MagicMock) -> None:
    # Override the service using the container fixture
    with container.override(HelloService, instance=hello_service_mock):
        client: Client = Client()
        response = client.get("/hello")

    assert response.status_code == 200
    assert b"Hello from pytest mock!" in response.content
    hello_service_mock.get_message.assert_called_once()
```

Alternatively, you can use pytest's autouse fixture to automatically override services for all tests in a module or class:

```python
from typing import Iterator
from unittest import mock

import pytest
from django.test import Client

from anydi import Container
from your_module import HelloService


@pytest.fixture(autouse=True)
def override_hello_service(container: Container) -> Iterator[mock.MagicMock]:
    """Automatically override HelloService for all tests."""
    hello_service_mock = mock.MagicMock(spec=HelloService)
    hello_service_mock.get_message.return_value = "Mocked message"

    with container.override(HelloService, instance=hello_service_mock):
        yield hello_service_mock


def test_hello_view(client: Client, hello_service_mock: mock.MagicMock) -> None:
    response = client.get("/hello")

    assert response.status_code == 200
    assert b"Mocked message" in response.content
    hello_service_mock.get_message.assert_called_once()
```

Both approaches provide flexible ways to mock dependencies in your tests, allowing you to test your Django views and business logic in isolation.

## Django Ninja

Install `anydi` with `Django Ninja` support:

```sh
pip install 'anydi-django[ninja]'
```

If you are using the [Django Ninja](https://django-ninja.dev/) framework, you can enable dependency injection by setting the `PATCH_NINJA` to `True`.

```python
ANYDI = {
    "PATCH_NINJA": True,
}
```

This setting will modify the `Django Ninja framework` to support dependency injection.

```python
from typing import Any

import anydi
from django.http import HttpRequest
from ninja import Router

from your_module import HelloService


router = Router()

@router.get("/hello")
def hello(request: HttpRequest, hello_service: HelloService = anydi.auto) -> dict[str, Any]:
    return {
        "message": hello_service.get_message(),
    }
```

The `HelloService` will be automatically injected into the hello endpoint using the provided marker `anydi.auto`.

### Testing Django Ninja endpoints

Testing Django Ninja endpoints works the same way as testing regular Django views. You can use the same testing approaches described in the [Testing](#testing) section above with `container.override` or the pytest `container` fixture.
