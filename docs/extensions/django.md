# Django Extension

## Quick Start

Add `anydi.ext.django` to the **bottom** of your `INSTALLED_APPS` setting in your `Django` settings file:

```python
INSTALLED_APPS = [
    ...
    "anydi.ext.django",
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

* `CONTAINER_FACTORY: str | None` - Specifies the factory function used to create the container. If not provided, the default container factory will be utilized.
* `REGISTER_SETTINGS: bool` - If `True`, the container will register the Django settings within it.
* `REGISTER_COMPONENTS: bool` - If `True`, the container will register Django components such as the database and cache.
* `INJECT_URLCONF: str | Sequence[str] | None` - Specifies the URL configuration where dependencies should be injected.
* `MODULES: Sequence[str]` - Lists the modules to be scanned for dependencies.
* `SCAN_PACKAGES: Sequence[str]` - Designates the packages to be scanned for dependencies.
* `PATCH_NINJA: bool` - If `True`, the container will modify the `ninja` framework to support dependency injection.

## Django Ninja

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
    "anydi.ext.django.middleware.request_scoped_middleware",
    ...
]
```

With this setup, you can define and utilize `request`-scoped dependencies throughout your application.
Additionally, `HttpRequest` dependencies are automatically available in request-scoped providers,
allowing convenient access to the request object and its data in these dependencies.
