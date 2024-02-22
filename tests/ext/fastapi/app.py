import typing as t

from fastapi import Body, Depends, FastAPI
from starlette.middleware import Middleware
from typing_extensions import Annotated

import initdi.ext.fastapi
from initdi.ext.fastapi import Inject
from initdi.ext.starlette.middleware import RequestScopedMiddleware

from tests.ext.fixtures import Mail, MailService, User, UserService

di = initdi.InitDI(strict=True)


@di.provider(scope="singleton")
def prefix() -> Annotated[str, "prefix"]:
    return "Hello, "


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
    user: Annotated[User, Depends(get_user)],
    mail_service: Annotated[MailService, Inject()],
    prefix: Annotated[Annotated[str, "prefix"], Inject()],
    message: Annotated[str, Body(embed=True)],
) -> t.Any:
    return await mail_service.send_mail(email=user.email, message=prefix + message)


initdi.ext.fastapi.install(app, di)
