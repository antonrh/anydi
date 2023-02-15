import typing as t

import pytest

from pyxdi._async import AsyncDI

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
