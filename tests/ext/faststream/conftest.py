import pytest
from faststream.redis import RedisBroker

from anydi import Container
from anydi.ext.faststream import get_container

from .app import broker as _broker


@pytest.fixture(scope="session")
def broker() -> RedisBroker:
    return _broker


@pytest.fixture
def container(broker: RedisBroker) -> Container:
    return get_container(broker)
