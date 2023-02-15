import typing as t

import pytest

from pyxdi._async import AsyncDI

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


async def test_get_and_set_with_request_context(di: AsyncDI) -> None:
    @di.provide(scope="request")
    def service(ident: str) -> Service:
        return Service(ident=ident)

    async with di.request_context() as ctx:
        ctx.set(str, "test")

        assert (await di.get(Service)).ident == "test"
