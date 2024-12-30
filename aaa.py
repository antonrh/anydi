import dataclasses
import time
from dataclasses import field
from unittest import mock

from anydi import Container

@dataclasses.dataclass
class User:
    name: str


@dataclasses.dataclass
class UserRepo:
    users: list[User] = field(default_factory=list)
    name: str = "UserRepo"

    def all(self):
        return self.users


@dataclasses.dataclass
class UserService:
    __scope__ = "singleton"

    repo: UserRepo

container = Container(strict=False, testing=True)


@container.provider(scope="singleton")
def user_repo() -> UserRepo:
    return UserRepo(users=[User(name="John")])


@container.provider(scope="singleton")
def user_service(repo: UserRepo) -> UserService:
    return UserService(repo=repo)


service = container.resolve(UserService)
repo_mock = mock.MagicMock(spec=UserRepo)
repo_mock.all.return_value = [User(name="Mock")]


print(service.repo.users)


with container.override(UserRepo, repo_mock):
    print(service.repo.all())
