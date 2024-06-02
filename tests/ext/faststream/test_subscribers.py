from faststream.redis import RedisBroker, TestRedisBroker

from anydi import Container

from tests.ext.faststream.app import UserMessage
from tests.ext.fixtures import UserService


async def test_handle(broker: RedisBroker, container: Container) -> None:
    async with TestRedisBroker(broker) as br:
        await br.publish(UserMessage(id=1, email="test@mail.com"), channel="test-in")

    user_service = container.resolve(UserService)

    user = await user_service.get_user_by_id(1)

    assert user.email == "test@mail.com"
