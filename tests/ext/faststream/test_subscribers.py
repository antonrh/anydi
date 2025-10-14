from typing import Any

import pytest
from faststream.redis import RedisBroker, TestRedisBroker
from pydantic import BaseModel

import anydi.ext.faststream
from anydi import Container
from anydi.ext.faststream import Inject

from tests.ext.fixtures import UserService


class UserMessage(BaseModel):
    id: int
    email: str


@pytest.fixture(scope="session")
def container() -> Container:
    container = Container()

    @container.provider(scope="singleton")
    def provide_user_service() -> UserService:
        return UserService()

    return container


@pytest.fixture(scope="session")
def broker(container: Container) -> RedisBroker:
    broker = RedisBroker()

    @broker.subscriber("test-in")
    async def create_user(
        message: UserMessage,
        user_service: UserService = Inject(),
    ) -> Any:
        return await user_service.create_user(id_=message.id, email=message.email)

    anydi.ext.faststream.install(broker, container)

    return broker


async def test_handle(broker: RedisBroker, container: Container) -> None:
    user_service = container.resolve(UserService)

    async with TestRedisBroker(broker) as br:
        await br.publish(UserMessage(id=1, email="test@mail.com"), channel="test-in")

    user = await user_service.get_user_by_id(1)

    assert user.email == "test@mail.com"
