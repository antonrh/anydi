import abc
import typing as t

from examples.common.domain import User


class UserRepository(abc.ABC):
    @abc.abstractmethod
    def all(self) -> t.List[User]:
        pass

    @abc.abstractmethod
    def add(self, user: User) -> None:
        pass

    @abc.abstractmethod
    def get(self, user_id: str) -> t.Optional[User]:
        pass


class InMemoryUserRepository(UserRepository):
    def __init__(self) -> None:
        self.data: t.Dict[str, User] = {}

    def all(self) -> t.List[User]:
        return list(self.data.values())

    def add(self, user: User) -> None:
        self.data[user.id] = user

    def get(self, user_id: str) -> t.Optional[User]:
        return self.data.get(user_id)
