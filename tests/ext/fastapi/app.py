import typing as t

import fastapi
from starlette.middleware import Middleware

import pyxdi.ext.fastapi
from pyxdi.ext.fastapi import Inject
from pyxdi.ext.starlette.middleware import RequestScopedMiddleware

from tests.ext.fixtures import Mail, MailService, User, UserService

di = pyxdi.PyxDI()


@di.provider(scope="singleton")
def user_service() -> UserService:
    return UserService()


@di.provider(scope="request")
def mail_service() -> MailService:
    return MailService()


async def get_user(user_service: UserService = Inject()) -> User:
    return await user_service.get_user()


app = fastapi.FastAPI(middleware=[Middleware(RequestScopedMiddleware, di=di)])


@app.post("/send-mail", response_model=Mail)
async def send_email(
    user: User = fastapi.Depends(get_user),
    mail_service: MailService = Inject(),
    message: str = fastapi.Body(embed=True),
) -> t.Any:
    return await mail_service.send_mail(email=user.email, message=message)


pyxdi.ext.fastapi.install(app, di)
