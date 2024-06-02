# FastStream Extension

Integrating `AnyDI` with [`FastStream`](https://faststream.airt.ai/latest/) is straightforward. Since `FastStream` uses [`FastDepends`](https://github.com/Lancetnik/FastDepends) library, there is a simple workaround for using the two together using custom `Inject` parameter instead of standard `Depends`.

Here's an example of how to make them work together:


```python
from faststream.redis import RedisBroker

import anydi.ext.faststream
from anydi import Container
from anydi.ext.faststream import Inject


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
    hello_service: HelloService = Inject(),
) -> str:
    return await hello_service.say_hello(name=name)


anydi.ext.faststream.install(broker, container)
```

!!! note

    To detect a dependency interface, provide a valid type annotation.
