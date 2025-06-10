from typing import cast

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from anydi import auto
from anydi.ext.starlette.middleware import RequestScopedMiddleware
from anydi.testing import TestContainer

from tests.ext.fixtures import MailService, UserService

container = TestContainer()


@container.provider(scope="singleton")
def user_service() -> UserService:
    return UserService()


@container.provider(scope="singleton")
def mail_service() -> MailService:
    return MailService()


@container.inject
async def send_email(
    request: Request,
    user_service: UserService = auto,
    mail_service: MailService = auto,
) -> JSONResponse:
    data = await request.json()
    message = cast(str, data.get("message"))
    user = await user_service.get_user()
    mail = await mail_service.send_mail(email=user.email, message=message)
    return JSONResponse(
        {
            "email": user.email,
            "message": mail.message,
        }
    )


app = Starlette(
    routes=[
        Route("/send-mail", send_email, methods=["POST"]),
    ],
    middleware=[Middleware(RequestScopedMiddleware, container=container)],
)

app.state.container = container
