import typing as t
from dataclasses import dataclass

from examples.basic.models import User
from examples.basic.repositories import UserRepository


@dataclass
class UserService:
    user_repository: UserRepository

    def get_users(self) -> t.List[User]:
        return self.user_repository.all()

    def create_user(self, email: str) -> User:
        user = User(email=email)
        self.user_repository.add(user)
        return user

    def get_user(self, email: str) -> t.Optional[User]:
        return self.user_repository.get_by_email(email)
