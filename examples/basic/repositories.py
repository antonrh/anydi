import abc
import typing as t

from examples.basic.models import User, UserId


class UserRepository(abc.ABC):
    @abc.abstractmethod
    def all(self) -> t.List[User]:
        pass

    @abc.abstractmethod
    def add(self, user: User) -> None:
        pass

    @abc.abstractmethod
    def get_by_email(self, email: str) -> t.Optional[User]:
        pass


class InMemoryUserRepository(UserRepository):
    def __init__(self) -> None:
        self.data: t.Dict[UserId, User] = {}

    def all(self) -> t.List[User]:
        return list(self.data.values())

    def add(self, user: User) -> None:
        self.data[user.id] = user

    def get_by_email(self, email: str) -> t.Optional[User]:
        try:
            return [user for user in self.data.values() if user.email == email][0]
        except IndexError:
            return None
