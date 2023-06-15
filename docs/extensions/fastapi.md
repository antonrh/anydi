# FastAPI Extension

Integrating `PyxDI` with `FastAPI` is straightforward. Since `FastAPI` comes with its own internal dependency injection
mechanism, there is a simple workaround for using the two together using custom `Inject` parameter instead of standard `Depends`.

Here's an example of how to make them work together:


```python
import fastapi
from fastapi import Path
import pyxdi.ext.fastapi
from pyxdi.ext.fastapi import Inject


class HelloService:
    async def say_hello(self, name: str) -> str:
        return f"Hello, {name}"


di = pyxdi.PyxDI()


@di.provider
def hello_service() -> HelloService:
    return HelloService()


app = fastapi.FastAPI()


@app.get("/hello/{name}")
async def say_hello(
    name: str = Path(),
    hello_service: HelloService = Inject(),
) -> str:
    return await hello_service.say_hello(name=name)


pyxdi.ext.fastapi.install(app, di)
```

!!! note

    To detect a dependency interface, provide a valid type annotation.


## Lifespan support

If you need to use `PyxDI` resources in your `FastAPI` application, you can easily integrate them by including `PyxDI`
startup and shutdown events in the `FastAPI` application's lifecycle events.

To do this synchronously, use the following code:

```python
import fastapi
import pyxdi.ext.fastapi


di = pyxdi.PyxDI()

app = fastapi.FastAPI(on_startup=[di.start], on_shutdown=[di.close])
```

And if you need to use asynchronous resources, use the following code:

```python
import fastapi
import pyxdi.ext.fastapi


di = pyxdi.PyxDI()

app = fastapi.FastAPI(on_startup=[di.astart], on_shutdown=[di.aclose])
```

## Request Scope

To utilize `request` scoped dependencies in your `FastAPI` application with `PyxDI`, you can make use of the
`RequestScopedMiddleware`. This middleware enables the creation of request-specific dependency instances,
which are instantiated and provided to the relevant request handlers throughout the lifetime of each request.

```python
from dataclasses import dataclass

import fastapi
from starlette.middleware import Middleware
from starlette.requests import Request

import pyxdi.ext.fastapi
from pyxdi.ext.fastapi import Inject, RequestScopedMiddleware, get_current_request


@dataclass
class RequestService:
    request: Request

    async def get_info(self) -> str:
        return f"{self.request.method} {self.request.url.path}"


di = pyxdi.PyxDI()


@di.provider(scope="request")
def request() -> Request:
    return get_current_request()


@di.provider(scope="request")
def request_service(request: Request) -> RequestService:
    return RequestService(request=request)


app = fastapi.FastAPI(
    middleware=[Middleware(RequestScopedMiddleware, di=di)],
)


@app.get("/request-info")
async def get_request_info(
        request_service: RequestService = Inject(),
) -> str:
    return await request_service.get_info()


pyxdi.ext.fastapi.install(app, di)
```
