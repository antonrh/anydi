from collections.abc import AsyncIterator

import pytest

from anydi.ext.django import container


@pytest.fixture(scope="session", autouse=True)
async def start_container() -> AsyncIterator[None]:
    await container.astart()
    yield
    await container.aclose()
