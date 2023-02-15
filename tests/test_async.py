import typing as t

import anyio.to_thread
import pytest

from pyxdi._async import AsyncDI  # noqa
from pyxdi._core import DependencyParam  # noqa

from tests.fixtures import Service

pytestmark = pytest.mark.anyio


@pytest.fixture
def di() -> AsyncDI:
    return AsyncDI()


async def test_close(di: AsyncDI) -> None:
    events = []

    def dep1() -> t.Iterator[str]:
        events.append("dep1:before")
        yield "test"
        events.append("dep1:after")

    di.bind(str, dep1, scope="singleton")

    assert await di.get(str) == "test"

    await di.close()

    assert events == ["dep1:before", "dep1:after"]


async def test_bind_transient_scoped_generator_provider(di: AsyncDI) -> None:
    ident = "test"

    def provider() -> t.Iterator[Service]:
        service = Service(ident=ident)
        service.events.append("before")
        yield service
        service.events.append("after")

    di.bind(Service, provider, scope="transient")

    service = await di.get(Service)

    assert service.ident == "test"
    assert service.events == ["before", "after"]


async def test_bind_transient_scoped_async_generator_provider(di: AsyncDI) -> None:
    ident = "test"

    async def provider() -> t.AsyncIterator[Service]:
        service = Service(ident=ident)
        service.events.append("before")
        yield service
        service.events.append("after")

    di.bind(Service, provider, scope="transient")

    service = await di.get(Service)

    assert service.ident == "test"
    assert service.events == ["before", "after"]


async def test_bind_request_scoped_async_generator_provider(di: AsyncDI) -> None:
    ident = "test"

    async def provider() -> t.AsyncIterator[Service]:
        service = Service(ident=ident)
        service.events.append("before")
        yield service
        service.events.append("after")

    di.bind(Service, provider, scope="request")

    async with di.request_context():
        service = await di.get(Service)

    assert service.ident == "test"
    assert service.events == ["before", "after"]


async def test_get_and_set_with_request_context(di: AsyncDI) -> None:
    @di.provide(scope="request")
    def service(ident: str) -> Service:
        return Service(ident=ident)

    async with di.request_context() as ctx:
        ctx.set(str, "test")

        assert (await di.get(Service)).ident == "test"


async def test_get_request_scoped_not_started(di: AsyncDI) -> None:
    ident = "test"

    def provider() -> Service:
        return Service(ident=ident)

    di.bind(Service, provider, scope="request")

    with pytest.raises(LookupError) as exc_info:
        await di.get(Service)

    assert str(exc_info.value) == "Request context is not started."


async def test_get_provider_arguments(di: AsyncDI) -> None:
    @di.provide()
    def a() -> int:
        return 10

    @di.provide()
    def b() -> float:
        return 1.0

    @di.provide()
    def c() -> str:
        return "test"

    @di.provide()
    def service(a: int, /, b: float, *, c: str) -> Service:
        ident = f"{a}/{b}/{c}"
        return Service(ident=ident)

    assert (await di.get(Service)).ident == "10/1.0/test"


async def test_inject_callable_with_async_target(di: AsyncDI) -> None:
    @di.provide()
    async def ident() -> str:
        return "1000"

    @di.provide()
    def service(ident: str) -> Service:
        return Service(ident=ident)

    @di.inject_callable
    async def func(name: str, service: Service = DependencyParam()) -> str:
        return f"{name} = {service.ident}"

    result = await func(name="service ident")

    assert result == "service ident = 1000"


async def test_inject_callable_with_sync_target(di: AsyncDI) -> None:
    @di.provide()
    def ident() -> str:
        return "1000"

    @di.provide()
    async def service(ident: str) -> Service:
        return Service(ident=ident)

    @di.inject_callable
    def func(name: str, service: Service = DependencyParam()) -> str:
        return f"{name} = {service.ident}"

    result = await anyio.to_thread.run_sync(func, "service ident")

    assert result == "service ident = 1000"
