# FastAPI Extension

Integrating `AnyDI` with `FastAPI` is straightforward. Since `FastAPI` comes with its own internal dependency injection
mechanism, there is a simple workaround for using the two together using `Provide` annotation or `Inject` marker instead of standard `Depends`.


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
from anydi import Container, Inject
from anydi.ext.fastapi import RequestScopedMiddleware


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


## WebSocket Support

`AnyDI` provides full support for WebSocket endpoints in FastAPI, including a dedicated `websocket` scope for managing
connection-specific state. The `websocket` scope is automatically registered when you call `anydi.ext.fastapi.install()`.

### WebSocket Scope

The `websocket` scope is registered with `request` as its parent scope, creating the hierarchy: `singleton` → `request` → `websocket`.
This means websocket-scoped dependencies can access both request-scoped and singleton dependencies.

The `websocket` scope allows you to create dependencies that:

- Are created once per WebSocket connection
- Persist across all messages within a connection
- Are automatically cleaned up when the connection closes
- Are isolated between different concurrent connections
- Can depend on request-scoped and singleton dependencies

### Basic WebSocket Example

Here's a simple example of using dependency injection in a WebSocket endpoint:

```python
from fastapi import FastAPI, WebSocket
from starlette.middleware import Middleware

import anydi.ext.fastapi
from anydi import Container, Provide
from anydi.ext.fastapi import RequestScopedMiddleware


class ConnectionState:
    """Tracks state for a single WebSocket connection."""

    def __init__(self) -> None:
        self.message_count = 0

    def process(self, message: str) -> str:
        self.message_count += 1
        return f"Message #{self.message_count}: {message}"


container = Container()

# WebSocket scope is automatically registered by install() with request as parent
# but you can also register it manually if needed:
# container.register_scope("websocket", parents=["request"])


@container.provider(scope="websocket")
def connection_state() -> ConnectionState:
    """Provides connection-specific state."""
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

In this example, each WebSocket connection gets its own `ConnectionState` instance that persists across all messages
within that connection. When the connection closes, the instance is automatically cleaned up.

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

The `WebSocket` object is automatically available in both `request` and `websocket` scoped providers:

```python
from starlette.websockets import WebSocket


@container.provider(scope="websocket")
def connection_info(websocket: WebSocket) -> dict:
    """Extract connection info from the WebSocket."""
    return {
        "client": websocket.client.host if websocket.client else "unknown",
        "headers": dict(websocket.headers),
    }


@app.websocket("/ws/info")
async def websocket_info(
    websocket: WebSocket,
    info: Provide[dict],
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
@container.provider(scope="request")
def request_id() -> str:
    import uuid
    return str(uuid.uuid4())


@container.provider(scope="websocket")
def connection_tracker(request_id: str) -> ConnectionTracker:
    return ConnectionTracker(connection_id=request_id)
```
