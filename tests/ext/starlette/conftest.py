from typing import cast

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from anydi import Container

from .app import app as _app


@pytest.fixture(scope="session")
def app() -> Starlette:
    return _app


@pytest.fixture(scope="session")
def container(app: Starlette) -> Container:
    return cast(Container, app.state.container)


@pytest.fixture
def client(app: Starlette) -> TestClient:
    return TestClient(app)
