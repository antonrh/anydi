import typing as t

import fastapi

import pyxdi.ext.fastapi
from pyxdi.ext.fastapi import Inject

from tests.ext.fixtures import Mail, MailService, User, UserService

di = pyxdi.PyxDI()


@di.provider(scope="singleton")
def user_service() -> UserService:
    return UserService()


@di.provider(scope="singleton")
def mail_service() -> MailService:
    return MailService()


async def get_user(user_service: UserService = Inject()) -> User:
    return await user_service.get_user()


app = fastapi.FastAPI()


@app.post("/send-mail", response_model=Mail)
async def send_email(
    user: User = fastapi.Depends(get_user),
    mail_service: MailService = Inject(),
    message: str = fastapi.Body(embed=True),
) -> t.Any:
    return await mail_service.send_mail(email=user.email, message=message)


@app.post("/send-mail-lazy", response_model=Mail)
async def send_email_lazy(
    user: User = fastapi.Depends(get_user),
    mail_service: MailService = Inject(lazy=True),
    message: str = fastapi.Body(embed=True),
) -> t.Any:
    if message == "lazy":
        return Mail(email=user.email, message=message)
    return await mail_service.send_mail(email=user.email, message=message)


pyxdi.ext.fastapi.install(app, di)
