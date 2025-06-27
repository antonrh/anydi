from typing import Annotated, Any

from fastapi import Body, Depends, FastAPI
from starlette.middleware import Middleware

import anydi.ext.fastapi
from anydi.ext.fastapi import Inject
from anydi.ext.starlette.middleware import RequestScopedMiddleware
from anydi.testing import TestContainer

from tests.ext.fixtures import Mail, MailService, User, UserService

container = TestContainer()


@container.provider(scope="singleton")
def message1() -> Annotated[str, "message1"]:
    return "message1"


@container.provider(scope="singleton")
def message1_a() -> Annotated[str, "message1", "a"]:
    return "message1_a"


@container.provider(scope="singleton")
def message1_a_b() -> Annotated[str, "message1", "a", "b"]:
    return "message1_a_b"


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
    message1_a: Annotated[Annotated[str, "message1", "a"], Inject()],
    message1_a_b: Annotated[Annotated[str, "message1", "a", "b"], Inject()],
    message2: Annotated[str, "message2"] = Inject(),
) -> Any:
    return [
        message1,
        message1_a,
        message1_a_b,
        message2,
    ]


anydi.ext.fastapi.install(app, container)
