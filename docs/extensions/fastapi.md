# FastAPI Extension

Integrating `AnyDI` with `FastAPI` is straightforward. Since `FastAPI` comes with its own internal dependency injection
mechanism, there is a simple workaround for using the two together using custom `Inject` parameter instead of standard `Depends`.

Here's an example of how to make them work together:


```python
from fastapi import FastAPI, Path

import anydi.ext.fastapi
from anydi import Container
from anydi.ext.fastapi import Inject


class HelloService:
    async def say_hello(self, name: str) -> str:
        return f"Hello, {name}"


container = Container()


@container.provider(scope="singleton")
def hello_service() -> HelloService:
    return HelloService()


app = FastAPI()


@app.get("/hello/{name}")
async def say_hello(
    name: str = Path(),
    hello_service: HelloService = Inject(),
) -> str:
    return await hello_service.say_hello(name=name)


anydi.ext.fastapi.install(app, container)
```

!!! note

    To detect a dependency interface, provide a valid type annotation.

`AnyDI` also supports `Annotated` type hints, so you can use `Annotated[...]` instead of `... = Inject()` using `FastAPI` version `0.95.0` or higher:

```python
from typing import Annotated

from fastapi import FastAPI, Path

import anydi.ext.fastapi
from anydi import Container
from anydi.ext.fastapi import Inject


class HelloService:
    async def say_hello(self, name: str) -> str:
        return f"Hello, {name}"


container = Container()


@container.provider(scope="singleton")
def hello_service() -> HelloService:
    return HelloService()


app = FastAPI()


@app.get("/hello/{name}")
async def say_hello(
    name: Annotated[str, Path()],
    hello_service: Annotated[HelloService, Inject()],
) -> str:
    return await hello_service.say_hello(name=name)


anydi.ext.fastapi.install(app, container)
```


## Lifespan support

If you need to use `AnyDI` resources in your `FastAPI` application, you can easily integrate them by including `AnyDI`
startup and shutdown events in the `FastAPI` application's lifecycle events.

To do this, use the following code:

```python
from fastapi import FastAPI

from anydi import Container

container = Container()

app = FastAPI(on_startup=[container.astart], on_shutdown=[container.aclose])
```

or using lifespan handler:

```python
import contextlib
from typing import AsyncIterator

from fastapi import FastAPI

from anydi import Container

container = Container()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await container.astart()
    yield
    await container.aclose()


app = FastAPI(lifespan=lifespan)
```


## Request Scope

To enable `request`-scoped dependencies in your `FastAPI` application using `AnyDI`, use the `RequestScopedMiddleware`.
This middleware allows for the creation of dependencies tied to the lifecycle of each request, including access to the `Request` object itself.

Here's an example setup:

```python
from dataclasses import dataclass

from fastapi import FastAPI, Path, Request
from starlette.middleware import Middleware

import anydi.ext.fastapi
from anydi import Container
from anydi.ext.fastapi import Inject, RequestScopedMiddleware


@dataclass(kw_only=True)
class User:
    id: str
    email: str


class UserService:
    def __init__(self, request: Request) -> None:
        self.request = request

    async def get_user(self, user_id: str) -> User:
        # Use request headers, IP, etc., from the Request object as needed
        client_ip = self.request.client.host
        return User(id=user_id, email=f"user-{client_ip}@mail.com")


container = Container()


@container.provider(scope="request")
def user_service(request: Request) -> UserService:
    return UserService(request=request)


app = FastAPI(
    middleware=[
        Middleware(RequestScopedMiddleware, container=container),
    ],
)


@app.get("/user/{user_id}")
async def get_user(
    user_id: str = Path(),
    user_service: UserService = Inject(),
) -> dict:
    user = await user_service.get_user(user_id=user_id)
    return {"id": user.id, "email": user.email}


# Install AnyDI support in FastAPI
anydi.ext.fastapi.install(app, container)
```

With this setup, you can define and utilize request-scoped dependencies throughout your application.
Additionally, `Request` dependencies are automatically available in request-scoped providers,
allowing convenient access to the request object and its data in these dependencies.
