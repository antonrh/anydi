import logging
import typing as t

import fastapi
import pytest

import pyxdi.ext.fastapi
from pyxdi.ext.fastapi import Inject

from tests.ext.fixtures import Mail, MailService


def test_auto_register(caplog: pytest.LogCaptureFixture) -> None:
    di = pyxdi.PyxDI(auto_register=True)

    app = fastapi.FastAPI()

    @app.post("/send-mail", response_model=Mail)
    async def send_email(
        mail_service: MailService = Inject(),
    ) -> t.Any:
        return await mail_service.send_mail(email="test@mail.com", message="test")

    with caplog.at_level(logging.WARNING, logger="pyxdi.ext.fastapi"):
        pyxdi.ext.fastapi.install(app, di)

        assert caplog.messages == [
            "Route `tests.ext.fastapi.test_auto_register.test_auto_register.<locals>"
            ".send_email` injected parameter `mail_service` with an annotation of "
            "`tests.ext.fixtures.MailService` is not registered. It will be "
            "registered at runtime with the first call."
        ]
