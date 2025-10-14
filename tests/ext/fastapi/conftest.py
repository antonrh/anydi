from typing import cast

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from anydi import Container

from .app import app as _app


@pytest.fixture(scope="session")
def app() -> FastAPI:
    return _app


@pytest.fixture(scope="session")
def container(app: FastAPI) -> Container:
    return cast(Container, app.state.container)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)
