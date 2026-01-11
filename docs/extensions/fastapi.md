# FastAPI Extension

You can use `AnyDI` with `FastAPI` easily. Since `FastAPI` has its own dependency injection, you can use `Provide` annotation or `Inject` marker instead of the standard `Depends`.


```python
from typing import Annotated

from fastapi import FastAPI, Path

import anydi.ext.fastapi
from anydi import Container, Provide


class HelloService:
    async def say_hello(self, name: str) -> str:
        return f"Hello, {name}"


container = Container()
container.register(HelloService)

app = FastAPI()


@app.get("/hello/{name}")
async def say_hello(
    name: Annotated[str, Path()],
    hello_service: Provide[HelloService],
) -> str:
    return await hello_service.say_hello(name=name)


anydi.ext.fastapi.install(app, container)
```

!!! note

    To detect a dependency interface, provide a valid type annotation.

    `Provide[Service]` is equivalent to `Annotated[Service, Inject()]`.

You can also use `Inject()` marker:

```python
@app.get("/hello/{name}")
async def say_hello(
    name: str = Path(),
    hello_service: HelloService = Inject(),
) -> str:
    return await hello_service.say_hello(name=name)
```


## Lifespan support

If you need to use `AnyDI` resources in your `FastAPI` application, you can add `AnyDI` startup and shutdown events to the `FastAPI` lifecycle events.

You can do this like this:

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

To use `request`-scoped dependencies in your `FastAPI` application, use the `RequestScopedMiddleware`. This middleware creates dependencies that are tied to each request lifecycle. You can also access the `Request` object.

Here is an example:

```python
from dataclasses import dataclass

from fastapi import FastAPI, Path, Request
from starlette.middleware import Middleware

import anydi.ext.fastapi
from anydi import Container, FromContext, Provide
from anydi.ext.fastapi import RequestScopedMiddleware


@dataclass
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
def user_service(request: FromContext[Request]) -> UserService:
    return UserService(request=request)


app = FastAPI(
    middleware=[
        Middleware(RequestScopedMiddleware, container=container),
    ],
)


@app.get("/user/{user_id}")
async def get_user(
    user_id: str,
    user_service: Provide[UserService],
) -> dict:
    user = await user_service.get_user(user_id=user_id)
    return {"id": user.id, "email": user.email}


# Install AnyDI support in FastAPI
anydi.ext.fastapi.install(app, container)
```

With this setup, you can use request-scoped dependencies in your application. The `Request` object is provided by the `RequestScopedMiddleware` and marked with `FromContext[Request]` to indicate it comes from the runtime context.


## WebSocket Support

`AnyDI` supports WebSocket endpoints in FastAPI with a dedicated `websocket` scope for connection-specific state. The `websocket` scope is registered automatically when you call `anydi.ext.fastapi.install()`.

### WebSocket scope

The `websocket` scope has `request` as parent scope. The hierarchy is: `singleton` → `request` → `websocket`. This means websocket-scoped dependencies can use both request-scoped and singleton dependencies.

The `websocket` scope lets you create dependencies that:

- Are created one time per WebSocket connection
- Stay alive for all messages in a connection
- Are cleaned up automatically when the connection closes
- Are isolated between different connections
- Can use request-scoped and singleton dependencies

### Basic WebSocket Example

Here's a simple example of using dependency injection in a WebSocket endpoint:

```python
from fastapi import FastAPI, WebSocket
from starlette.middleware import Middleware

import anydi.ext.fastapi
from anydi import Container, Provide
from anydi.ext.fastapi import RequestScopedMiddleware


class ConnectionState:
    def __init__(self) -> None:
        self.message_count = 0

    def process(self, message: str) -> str:
        self.message_count += 1
        return f"Message #{self.message_count}: {message}"


container = Container()


@container.provider(scope="websocket")
def connection_state() -> ConnectionState:
    return ConnectionState()


app = FastAPI(
    middleware=[
        Middleware(RequestScopedMiddleware, container=container),
    ]
)


@app.websocket("/ws/echo")
async def websocket_echo(
    websocket: WebSocket, state: Provide[ConnectionState],
) -> None:
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            if data == "quit":
                break
            response = state.process(data)
            await websocket.send_text(response)
    finally:
        await websocket.close()


anydi.ext.fastapi.install(app, container)
```

In this example, each WebSocket connection gets its own `ConnectionState` instance that stays alive for all messages in that connection. When the connection closes, the instance is cleaned up automatically.

### Resource Cleanup

WebSocket-scoped dependencies support automatic cleanup using generator-based providers:

```python
from collections.abc import Iterator


@container.provider(scope="websocket")
def database_connection() -> Iterator[DatabaseConnection]:
    # Setup: Create connection
    conn = DatabaseConnection()
    print(f"WebSocket connection opened: {conn.id}")

    yield conn

    # Cleanup: Close connection when WebSocket disconnects
    conn.close()
    print(f"WebSocket connection closed: {conn.id}")


@app.websocket("/ws/database")
async def websocket_database(
    websocket: WebSocket,
    db: Provide[DatabaseConnection],
) -> None:
    await websocket.accept()
    # Use the database connection
    data = await websocket.receive_text()
    result = await db.query(data)
    await websocket.send_json(result)
    await websocket.close()
    # Cleanup automatically happens here
```

### Accessing WebSocket Object

The `WebSocket` object is provided by the middleware in both `request` and `websocket` scoped providers. Use `FromContext[WebSocket]` to mark it as a runtime dependency:

```python
from dataclasses import dataclass
from typing import Any

from starlette.websockets import WebSocket

from anydi import FromContext


@dataclass
class ConnectionInfo:
    client: str
    headers: dict[str, Any]


@container.provider(scope="websocket")
def connection_info(websocket: FromContext[WebSocket]) -> ConnectionInfo:
    return ConnectionInfo(
        client=websocket.client.host if websocket.client else "unknown",
        headers=dict(websocket.headers),
    )


@app.websocket("/ws/info")
async def websocket_info(
    websocket: WebSocket,
    info: Provide[ConnectionInfo],
) -> None:
    await websocket.accept()
    await websocket.send_json(info)
    await websocket.close()
```

### Concurrent Connections

Each WebSocket connection maintains its own isolated scope:

```python
# Connection 1 gets its own ConnectionState instance
# Connection 2 gets a different ConnectionState instance
# They don't interfere with each other

@app.websocket("/ws/concurrent")
async def websocket_concurrent(
    websocket: WebSocket,
    state: Provide[ConnectionState],
) -> None:
    await websocket.accept()
    # Each connection has isolated state
    while True:
        data = await websocket.receive_text()
        # state.message_count is independent per connection
        response = state.process(data)
        await websocket.send_text(response)
```

### Scope Hierarchy

Since `websocket` inherits from `request` scope, websocket-scoped providers can inject request-scoped dependencies:

```python
import uuid


@container.provider(scope="request")
def request_id() -> str:
    return str(uuid.uuid4())


@container.provider(scope="websocket")
def connection_tracker(request_id: str) -> ConnectionTracker:
    return ConnectionTracker(connection_id=request_id)
```
