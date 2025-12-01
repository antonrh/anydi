# FastStream Extension

Integrating `AnyDI` with [`FastStream`](https://faststream.airt.ai/latest/) is straightforward. Because `FastStream` relies on [`FastDepends`](https://github.com/Lancetnik/FastDepends), you can reuse the same `Provide[...]` annotation or `Inject()` marker style as with the FastAPI extension, rather than FastDepends' native `Depends`.

!!! warning "Version Requirement"

    Only FastStream >= 0.6 is supported. There are breaking changes between FastStream 0.5 and 0.6 versions that make earlier versions incompatible with this extension.

Here's an example of how to make them work together:


```python
from faststream.redis import RedisBroker

import anydi.ext.faststream
from anydi import Container, Provide


class GreetingService:
    async def greet(self, name: str) -> str:
        return f"Hello, {name}"


container = Container()


@container.provider(scope="singleton")
def greeting_service() -> GreetingService:
    return GreetingService()


broker = RedisBroker()


@broker.subscriber("greetings")
async def handle_greeting(
    name: str,
    service: Provide[GreetingService],
) -> str:
    return await service.greet(name=name)


anydi.ext.faststream.install(broker, container)
```

!!! note

    To detect a dependency interface, provide a valid type annotation.

    `Provide[Service]` is equivalent to `Annotated[Service, Inject()]`.

You can also use the `Inject()` marker as a default value:

```python
from anydi import Inject


@broker.subscriber("greetings")
async def handle_greeting(
    name: str,
    service: GreetingService = Inject(),
) -> str:
    return await service.greet(name=name)
```

## Using Request-Scoped Dependencies

To use request-scoped dependencies with FastStream, use the built-in `RequestScopedMiddleware` that wraps message handlers in a request context. This is useful for message-level resources:

```python
import uuid

from faststream.redis import RedisBroker

import anydi.ext.faststream
from anydi import Container, Provide
from anydi.ext.faststream import RequestScopedMiddleware


class MessageLogger:
    def __init__(self) -> None:
        self.message_id = str(uuid.uuid4())

    def log(self, text: str) -> None:
        print(f"[{self.message_id}] {text}")


container = Container()


@container.provider(scope="request")
def message_logger() -> MessageLogger:
    return MessageLogger()


broker = RedisBroker(middlewares=(RequestScopedMiddleware,))


@broker.subscriber("orders.process")
async def process_order(
    order_id: str,
    logger: Provide[MessageLogger],
) -> None:
    logger.log(f"Processing order {order_id}")
    logger.log("Order processed successfully")


anydi.ext.faststream.install(broker, container)
```

The `RequestScopedMiddleware` ensures that each message is processed within its own request context, allowing request-scoped dependencies to be properly resolved and isolated per message.

## Using Custom Scoped Dependencies

You can also use custom scopes with FastStream by creating a custom middleware for your specific scope:

```python
from functools import cached_property
from typing import Any

from faststream import BaseMiddleware, StreamMessage
from faststream.redis import RedisBroker

import anydi.ext.faststream
from anydi import Container, Provide
from anydi.ext.faststream import get_container_from_context


class BatchContext:
    """Context shared across messages in a batch."""

    def __init__(self, batch_id: str) -> None:
        self.batch_id = batch_id
        self.processed_count = 0


container = Container()

# Register custom "batch" scope
container.register_scope("batch")


@container.provider(scope="batch")
def batch_context() -> BatchContext:
    return BatchContext(batch_id="batch-123")


class BatchScopedMiddleware(BaseMiddleware):
    @cached_property
    def container(self) -> Container:
        return get_container_from_context(self.context)

    async def consume_scope(
        self, call_next: Any, msg: StreamMessage[Any]
    ) -> Any:
        async with self.container.ascoped_context("batch"):
            return await call_next(msg)


broker = RedisBroker(middlewares=(BatchScopedMiddleware,))


@broker.subscriber("batch.process")
async def process_message(
    message: str,
    ctx: Provide[BatchContext],
) -> None:
    ctx.processed_count += 1
    print(f"Batch {ctx.batch_id}: Processed {ctx.processed_count} messages")


anydi.ext.faststream.install(broker, container)
```

This pattern allows you to share state and resources across messages within a custom scope.
