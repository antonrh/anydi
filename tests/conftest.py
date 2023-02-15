import pytest


@pytest.fixture(scope="session", autouse=True)
def anyio_backend() -> str:
    return "asyncio"
