import logging
from typing import Any

import pytest
from fastapi import FastAPI

import anydi.ext.fastapi
from anydi import Container
from anydi.ext.fastapi import Inject

from tests.ext.fixtures import Mail, MailService


def test_auto_register(caplog: pytest.LogCaptureFixture) -> None:
    container = Container(strict=False)

    app = FastAPI()

    @app.post("/send-mail", response_model=Mail)
    async def send_email(
        mail_service: MailService = Inject(),
    ) -> Any:
        return await mail_service.send_mail(email="test@mail.com", message="test")

    with caplog.at_level(logging.DEBUG, logger="anydi"):
        anydi.ext.fastapi.install(app, container)

        assert caplog.messages == [
            "Callable `tests.ext.fastapi.test_auto_register.test_auto_register.<locals>"
            ".send_email` injected parameter `mail_service` with an annotation of "
            "`tests.ext.fixtures.MailService` is not registered. It will be "
            "registered at runtime with the first call because it is running in "
            "non-strict mode."
        ]
