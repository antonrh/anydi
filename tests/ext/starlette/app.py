import typing as t

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

import pyxdi
from pyxdi.ext.starlette.middleware import RequestScopedMiddleware

from tests.ext.fixtures import MailService, UserService

di = pyxdi.PyxDI()


@di.provider(scope="singleton")
def user_service() -> UserService:
    return UserService()


@di.provider(scope="singleton")
def mail_service() -> MailService:
    return MailService()


@di.inject
async def send_email(
    request: Request,
    user_service: UserService = pyxdi.dep,
    mail_service: MailService = pyxdi.dep,
) -> JSONResponse:
    data = await request.json()
    message = t.cast(str, data.get("message"))
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
    middleware=[Middleware(RequestScopedMiddleware, di=di)],
)

app.state.di = di
