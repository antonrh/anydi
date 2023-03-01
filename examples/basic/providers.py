import pyxdi
from examples.basic.repositories import InMemoryUserRepository, UserRepository
from examples.basic.services import UserService


@pyxdi.provider
def user_repository() -> UserRepository:
    return InMemoryUserRepository()


@pyxdi.provider
def user_service(user_repository: UserRepository) -> UserService:
    return UserService(user_repository=user_repository)
