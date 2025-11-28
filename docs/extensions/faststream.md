# FastStream Extension

Integrating `AnyDI` with [`FastStream`](https://faststream.airt.ai/latest/) is straightforward. Because `FastStream` relies on [`FastDepends`](https://github.com/Lancetnik/FastDepends), you can reuse the same `Provide[...]` annotation or `Inject()` marker style as with the FastAPI extension, rather than FastDepends' native `Depends`.

Here's an example of how to make them work together:


```python
from faststream.redis import RedisBroker

import anydi.ext.faststream
from anydi import Container, Provide


class HelloService:
    async def say_hello(self, name: str) -> str:
        return f"Hello, {name}"


container = Container()


@container.provider(scope="singleton")
def hello_service() -> HelloService:
    return HelloService()


broker = RedisBroker()


@broker.subscriber("hello")
async def say_hello(
    name: str,
    hello_service: Provide[HelloService],
) -> str:
    return await hello_service.say_hello(name=name)


anydi.ext.faststream.install(broker, container)
```

!!! note

    To detect a dependency interface, provide a valid type annotation.

    `Provide[Service]` is equivalent to `Annotated[Service, Inject()]`.

You can also use the default-value marker directly:

```python
from anydi import Inject


@broker.subscriber("hello")
async def say_hello(
    name: str,
    hello_service: HelloService = Inject(),
) -> str:
    return await hello_service.say_hello(name=name)
```
