from typing import Any

from faststream.redis import RedisBroker
from pydantic import BaseModel

import anydi.ext.faststream
from anydi import Container
from anydi.ext.faststream import Inject

from tests.ext.fixtures import UserService

container = Container(strict=True)


class UserMessage(BaseModel):
    id: int
    email: str


@container.provider(scope="singleton")
def provide_user_service() -> UserService:
    return UserService()


broker = RedisBroker()


@broker.subscriber("test-in")
async def create_user(
    message: UserMessage,
    user_service: UserService = Inject(),
) -> Any:
    return await user_service.create_user(id_=message.id, email=message.email)


anydi.ext.faststream.install(broker, container)
