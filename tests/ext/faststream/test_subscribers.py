import pytest
from faststream.redis import RedisBroker, TestRedisBroker
from pydantic import BaseModel

import anydi.ext.faststream
from anydi import Container, Inject, Provide
from anydi.ext.faststream import RequestScopedMiddleware

from tests.ext.fixtures import MailService


class EmailMessage(BaseModel):
    to: str
    subject: str
    body: str


class RequestContext:
    def __init__(self, request_id: str) -> None:
        self.request_id = request_id


container = Container()


@container.provider(scope="singleton")
def provide_mail_service() -> MailService:
    return MailService()


@container.provider(scope="request")
def request_context() -> RequestContext:
    return RequestContext(request_id="test-123")


# Storage for test results
_request_context_results: list[str] = []
_email_results: list[tuple[str, str]] = []


@pytest.fixture(scope="session")
def broker() -> RedisBroker:
    # Ensure FastStream's provide factory is set for this test
    from anydi._types import set_provide_factory
    from anydi.ext.faststream import _ProvideMarker

    set_provide_factory(_ProvideMarker)

    broker = RedisBroker(middlewares=(RequestScopedMiddleware,))

    # Subscriber with Inject() marker
    @broker.subscriber("email.send")
    async def send_email_with_inject(
        message: EmailMessage,
        mail_service: MailService = Inject(),
    ) -> None:
        result = await mail_service.send_mail(
            email=message.to, message=f"{message.subject}: {message.body}"
        )
        _email_results.append((result.email, result.message))

    # Subscriber with Provide annotation
    @broker.subscriber("email.notify")
    async def send_notification_with_provide(
        message: EmailMessage,
        mail_service: Provide[MailService],
    ) -> None:
        result = await mail_service.send_mail(
            email=message.to, message=f"{message.subject}: {message.body}"
        )
        _email_results.append((result.email, result.message))

    # Request-scoped subscriber with Inject() marker
    @broker.subscriber("request.process.inject")
    async def process_request_inject(
        message: str,
        ctx: RequestContext = Inject(),
    ) -> None:
        _request_context_results.append(f"{message}:{ctx.request_id}")

    # Request-scoped subscriber with Provide annotation
    @broker.subscriber("request.process.provide")
    async def process_request_provide(
        message: str,
        ctx: Provide[RequestContext],
    ) -> None:
        _request_context_results.append(f"{message}:{ctx.request_id}")

    anydi.ext.faststream.install(broker, container)

    return broker


async def test_singleton_dependency_with_inject_marker(
    broker: RedisBroker,
) -> None:
    """Test singleton dependency injection using Inject() marker."""
    _email_results.clear()

    async with TestRedisBroker(broker) as br:
        await br.publish(
            EmailMessage(
                to="user@example.com",
                subject="Welcome",
                body="Thanks for signing up!",
            ),
            channel="email.send",
        )

    assert len(_email_results) == 1
    assert _email_results[0] == ("user@example.com", "Welcome: Thanks for signing up!")


async def test_singleton_dependency_with_provide_annotation(
    broker: RedisBroker,
) -> None:
    """Test singleton dependency injection using Provide[T] annotation."""
    _email_results.clear()

    async with TestRedisBroker(broker) as br:
        await br.publish(
            EmailMessage(
                to="admin@example.com",
                subject="Alert",
                body="System notification",
            ),
            channel="email.notify",
        )

    assert len(_email_results) == 1
    assert _email_results[0] == ("admin@example.com", "Alert: System notification")


async def test_request_scoped_dependency_with_inject_marker(
    broker: RedisBroker,
) -> None:
    """Test request-scoped dependency injection with middleware using Inject()."""
    _request_context_results.clear()

    async with TestRedisBroker(broker) as br:
        await br.publish("order-1001", channel="request.process.inject")

    assert _request_context_results == ["order-1001:test-123"]


async def test_request_scoped_dependency_with_provide_annotation(
    broker: RedisBroker,
) -> None:
    """Test request-scoped dependency injection with middleware using Provide[T]."""
    _request_context_results.clear()

    async with TestRedisBroker(broker) as br:
        await br.publish("payment-2002", channel="request.process.provide")

    assert _request_context_results == ["payment-2002:test-123"]
