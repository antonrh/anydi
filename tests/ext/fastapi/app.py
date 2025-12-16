from dataclasses import dataclass
from itertools import count
from typing import Annotated, Any

from fastapi import Body, Depends, FastAPI, WebSocket
from starlette.middleware import Middleware

import anydi.ext.fastapi
from anydi import Container, Inject, Provide
from anydi.ext.starlette.middleware import RequestScopedMiddleware

from tests.ext.fixtures import Mail, MailService, User, UserService


@dataclass
class Message:
    content: str


class ConnectionState:
    """WebSocket-scoped connection state."""

    def __init__(self) -> None:
        self.message_count = 0

    def process(self, message: str) -> str:
        self.message_count += 1
        return f"Message #{self.message_count}: {message}"


class WebSocketLogger:
    """Singleton logger shared across all connections."""

    def __init__(self) -> None:
        self.connections: list[str] = []

    def log_connection(self, client_id: str) -> None:
        self.connections.append(client_id)


container = Container()


# Register websocket scope
container.register_scope("websocket")


@container.provider(scope="singleton")
def welcome_message() -> Annotated[Message, "message"]:
    return Message(content="Hello from the default message!")


@container.provider(scope="singleton")
def vip_message() -> Annotated[Message, "message", "vip"]:
    return Message(content="Hello VIP!")


_request_message_counter = count(1)


@container.provider(scope="request")
def request_message() -> Annotated[Message, "message", "request"]:
    number = next(_request_message_counter)
    return Message(content=f"Request scoped message #{number}")


@container.provider(scope="singleton")
def user_service() -> UserService:
    return UserService()


@container.provider(scope="singleton")
def mail_service() -> MailService:
    return MailService()


@container.provider(scope="websocket")
def connection_state() -> ConnectionState:
    return ConnectionState()


@container.provider(scope="singleton")
def websocket_logger() -> WebSocketLogger:
    return WebSocketLogger()


async def get_user(user_service: UserService = Inject()) -> User:
    return await user_service.get_user()


app = FastAPI(
    middleware=[
        Middleware(RequestScopedMiddleware, container=container),
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
    base_message: Annotated[
        Annotated[Message, "message"],
        Inject(),
    ],
    vip_message: Annotated[
        Annotated[Message, "message", "vip"],
        Inject(),
    ],
    request_message: Annotated[
        Annotated[Message, "message", "request"],
        Inject(),
    ],
) -> Any:
    return {
        "default": base_message.content,
        "vip": vip_message.content,
        "request": request_message.content,
    }


@app.websocket("/ws/echo")
async def websocket_echo(websocket: WebSocket, state: Provide[ConnectionState]) -> None:
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            if data == "quit":
                break
            response = state.process(data)
            await websocket.send_text(response)
    finally:
        await websocket.close()


@app.websocket("/ws/logger")
async def websocket_logger_endpoint(
    websocket: WebSocket, logger: Provide[WebSocketLogger]
) -> None:
    await websocket.accept()
    client_id = await websocket.receive_text()
    logger.log_connection(client_id)
    await websocket.send_text(f"Logged: {client_id}")
    await websocket.close()


@app.websocket("/ws/mail")
async def websocket_mail(
    websocket: WebSocket, mail_service: Provide[MailService]
) -> None:
    await websocket.accept()
    message = await websocket.receive_text()
    mail = await mail_service.send_mail("ws@example.com", message)
    await websocket.send_json({"email": mail.email, "message": mail.message})
    await websocket.close()


@app.websocket("/ws/request-message")
async def websocket_request_message(
    websocket: WebSocket,
    message: Annotated[Message, "message", "request"] = Inject(),
) -> None:
    await websocket.accept()
    await websocket.send_text(message.content)
    await websocket.close()


anydi.ext.fastapi.install(app, container)
