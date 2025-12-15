from typing import Annotated, Any

from fastapi import Body, Depends, FastAPI, WebSocket
from starlette.middleware import Middleware

import anydi.ext.fastapi
from anydi import Container, Inject, Provide
from anydi.ext.starlette.middleware import RequestScopedMiddleware
from anydi.ext.starlette.websocket_middleware import WebSocketScopedMiddleware

from tests.ext.fixtures import Mail, MailService, User, UserService

container = Container()


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


app = FastAPI(
    middleware=[
        Middleware(RequestScopedMiddleware, container=container),
        Middleware(WebSocketScopedMiddleware, container=container),
    ]
)


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


@app.post("/send-mail-provide", response_model=Mail)
async def send_email_provide(
    user: Annotated[User, Depends(get_user)],
    mail_service: Provide[MailService],
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


@app.websocket("/ws/echo")
async def websocket_echo(
    websocket: WebSocket,
    user_service: UserService = Inject(),
) -> None:
    """WebSocket endpoint that echoes messages using injected service."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            if data == "quit":
                break
            # Use injected singleton service
            user = await user_service.get_user()
            await websocket.send_json({"message": data, "user_email": user.email})
    finally:
        await websocket.close()


anydi.ext.fastapi.install(app, container)
