# FastAPI Extension

Integrating `InitDI` with `FastAPI` is straightforward. Since `FastAPI` comes with its own internal dependency injection
mechanism, there is a simple workaround for using the two together using custom `Inject` parameter instead of standard `Depends`.

Here's an example of how to make them work together:


```python
import fastapi
from fastapi import Path

import initdi.ext.fastapi
from initdi import InitDI
from initdi.ext.fastapi import Inject


class HelloService:
    async def say_hello(self, name: str) -> str:
        return f"Hello, {name}"


di = InitDI()


@di.provider(scope="singleton")
def hello_service() -> HelloService:
    return HelloService()


app = fastapi.FastAPI()


@app.get("/hello/{name}")
async def say_hello(
    name: str = Path(),
    hello_service: HelloService = Inject(),
) -> str:
    return await hello_service.say_hello(name=name)


initdi.ext.fastapi.install(app, di)
```

!!! note

    To detect a dependency interface, provide a valid type annotation.

`InitDI` also supports `Annotated` type hints, so you can use `Annotated[...]` instead of `... = Inject()` using `FastAPI` version `0.95.0` or higher:

```python
from typing import Annotated

import fastapi
from fastapi import Path

import initdi.ext.fastapi
from initdi import InitDI
from initdi.ext.fastapi import Inject


class HelloService:
    async def say_hello(self, name: str) -> str:
        return f"Hello, {name}"


di = InitDI()


@di.provider(scope="singleton")
def hello_service() -> HelloService:
    return HelloService()


app = fastapi.FastAPI()


@app.get("/hello/{name}")
async def say_hello(
    name: Annotated[str, Path()],
    hello_service: Annotated[HelloService, Inject()],
) -> str:
    return await hello_service.say_hello(name=name)


initdi.ext.fastapi.install(app, di)
```


## Lifespan support

If you need to use `InitDI` resources in your `FastAPI` application, you can easily integrate them by including `InitDI`
startup and shutdown events in the `FastAPI` application's lifecycle events.

To do this, use the following code:

```python
from fastapi import FastAPI

from initdi import InitDI

di = InitDI()

app = FastAPI(on_startup=[di.astart], on_shutdown=[di.aclose])
```

or using lifespan handler:

```python
import contextlib
from typing import AsyncIterator

from fastapi import FastAPI

from initdi import InitDI

di = InitDI()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await di.astart()
    yield
    await di.aclose()


app = FastAPI(lifespan=lifespan)
```


## Request Scope

To utilize `request` scoped dependencies in your `FastAPI` application with `InitDI`, you can make use of the
`RequestScopedMiddleware`. This middleware enables the creation of request-specific dependency instances,
which are instantiated and provided to the relevant request handlers throughout the lifetime of each request.

```python
from dataclasses import dataclass

from fastapi import FastAPI, Path
from starlette.middleware import Middleware

import initdi.ext.fastapi
from initdi import InitDI
from initdi.ext.fastapi import Inject, RequestScopedMiddleware


@dataclass
class User:
    id: str
    email: str = "user@mail.com"


@dataclass
class UserService:
    async def get_user(self, user_id: str) -> User:
        return User(id=user_id)


di = InitDI()


@di.provider(scope="request")
def user_service() -> UserService:
    return UserService()


app = FastAPI(
    middleware=[Middleware(RequestScopedMiddleware, di=di)],
)


@app.get("/user/{user_id}")
async def get_user(
    user_id: str = Path(),
    user_service: UserService = Inject(),
) -> str:
    user = await user_service.get_user(user_id=user_id)
    return user.email


initdi.ext.fastapi.install(app, di)
```
