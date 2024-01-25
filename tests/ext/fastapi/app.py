import typing as t

import typing_extensions as te
from fastapi import Body, Depends, FastAPI
from starlette.middleware import Middleware

import pyxdi.ext.fastapi
from pyxdi.ext.fastapi import Inject
from pyxdi.ext.starlette.middleware import RequestScopedMiddleware

from tests.ext.fixtures import Mail, MailService, User, UserService

di = pyxdi.PyxDI(strict=True)


@di.provider(scope="singleton")
def user_service() -> UserService:
    return UserService()


@di.provider(scope="request")
def mail_service() -> MailService:
    return MailService()


async def get_user(user_service: UserService = Inject()) -> User:
    return await user_service.get_user()


app = FastAPI(middleware=[Middleware(RequestScopedMiddleware, di=di)])


@app.post("/send-mail", response_model=Mail)
async def send_email(
    user: User = Depends(get_user),
    mail_service: MailService = Inject(),
    message: str = Body(embed=True),
) -> t.Any:
    return await mail_service.send_mail(email=user.email, message=message)


@app.post("/send-mail-annotated", response_model=Mail)
async def send_email_annotated(
    user: te.Annotated[User, Depends(get_user)],
    mail_service: te.Annotated[MailService, Inject()],
    message: te.Annotated[str, Body(embed=True)],
) -> t.Any:
    return await mail_service.send_mail(email=user.email, message=message)


pyxdi.ext.fastapi.install(app, di)
