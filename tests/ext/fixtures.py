from dataclasses import dataclass

TEST_EMAIL = "test@mail.com"


@dataclass
class User:
    id: int
    email: str


class UserService:
    def __init__(self) -> None:
        self._users: dict[int, User] = {}

    async def create_user(self, id_: int, email: str) -> User:
        user = User(id=id_, email=email)
        self._users[id_] = user
        return user

    async def get_user_by_id(self, id_: int) -> User:
        return self._users[id_]

    async def get_user(self) -> User:
        return User(id=1, email=TEST_EMAIL)


@dataclass
class Mail:
    email: str
    message: str


class MailService:
    async def send_mail(self, email: str, message: str) -> Mail:
        return Mail(email=email, message=message)
