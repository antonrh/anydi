import typing as t

import pyxdi
from examples.basic.models import User
from examples.basic.services import UserService


def get_users(user_service: UserService = pyxdi.dep) -> t.List[User]:
    return user_service.get_users()


def get_user(email: str, user_service: UserService = pyxdi.dep) -> User:
    user = user_service.get_user(email)
    if not user:
        raise Exception("User not found.")
    return user


def create_user(email: str, user_service: UserService = pyxdi.dep) -> User:
    return user_service.create_user(email=email)
