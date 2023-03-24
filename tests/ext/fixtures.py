from dataclasses import dataclass

TEST_EMAIL = "test@mail.com"


@dataclass
class User:
    id: int
    email: str


class UserService:
    async def get_user(self) -> User:
        return User(id=1, email=TEST_EMAIL)


@dataclass
class Mail:
    email: str
    message: str


class MailService:
    async def send_mail(self, email: str, message: str) -> Mail:
        return Mail(email=email, message=message)
