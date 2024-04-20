from typing import Any

from fastapi import Body, Depends, FastAPI
from starlette.middleware import Middleware
from typing_extensions import Annotated

import anydi.ext.fastapi
from anydi import Container
from anydi.ext.fastapi import Inject
from anydi.ext.starlette.middleware import RequestScopedMiddleware

from tests.ext.fixtures import Mail, MailService, User, UserService

container = Container(strict=True)


@container.provider(scope="singleton")
def message1() -> Annotated[str, "message1"]:
    return "message1"


@container.provider(scope="singleton")
def message2() -> Annotated[str, "message2"]:
    return "message2"


@container.provider(scope="singleton")
def user_service() -> UserService:
    return UserService()


@container.provider(scope="request")
def mail_service() -> MailService:
    return MailService()


async def get_user(user_service: UserService = Inject()) -> User:
    return await user_service.get_user()


app = FastAPI(middleware=[Middleware(RequestScopedMiddleware, container=container)])


@app.post("/send-mail", response_model=Mail)
async def send_email(
    user: User = Depends(get_user),
    mail_service: MailService = Inject(),
    message: str = Body(embed=True),
) -> Any:
    return await mail_service.send_mail(email=user.email, message=message)


@app.post("/send-mail-annotated", response_model=Mail)
async def send_email_annotated(
    user: Annotated[User, Depends(get_user)],
    mail_service: Annotated[MailService, Inject()],
    message: Annotated[str, Body(embed=True)],
) -> Any:
    return await mail_service.send_mail(email=user.email, message=message)


@app.get("/annotated-mixed")
def annotated_mixed(
    message1: Annotated[Annotated[str, "message1"], Inject()],
    message2: Annotated[str, "message2"] = Inject(),
) -> str:
    return f"{message1} - {message2}"


anydi.ext.fastapi.install(app, container)
