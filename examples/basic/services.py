import typing as t
from dataclasses import dataclass

from examples.common.domain import User
from examples.common.repository import UserRepository


@dataclass
class UserService:
    repository: UserRepository

    def get_users(self) -> t.List[User]:
        return self.repository.all()

    def create_user(self, email: str) -> User:
        user = User(email=email)
        self.repository.add(user)
        return user

    def get_user(self, user_id: str) -> t.Optional[User]:
        return self.repository.get(user_id)
