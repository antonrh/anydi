import typing as t
from dataclasses import dataclass

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

import pyxdi
from pyxdi.ext.starlette.middleware import RequestScopedMiddleware, get_request

from tests.ext.fixtures import MailService, UserService


@dataclass
class RequestService:
    request: Request

    async def get_info(self) -> str:
        return f"{self.request.method} {self.request.url.path}"


di = pyxdi.PyxDI()


@di.provider(scope="singleton")
def user_service() -> UserService:
    return UserService()


@di.provider(scope="singleton")
def mail_service() -> MailService:
    return MailService()


@di.provider(scope="request")
def request() -> Request:
    return get_request()


@di.provider(scope="request")
def request_service(request: Request) -> RequestService:
    return RequestService(request=request)


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


@di.inject
async def get_request_info(
    request: Request,
    request_service: RequestService = pyxdi.dep,
) -> JSONResponse:
    return JSONResponse({"request_info": await request_service.get_info()})


app = Starlette(
    routes=[
        Route("/send-mail", send_email, methods=["POST"]),
        Route("/request-info", get_request_info, methods=["GET"]),
    ],
    middleware=[Middleware(RequestScopedMiddleware, di=di)],
)

app.state.di = di
