import typing as t

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

import initdi

from .app import app as _app


@pytest.fixture(scope="session")
def app() -> Starlette:
    return _app


@pytest.fixture(scope="session")
def di(app: Starlette) -> initdi.InitDI:
    return t.cast(initdi.InitDI, app.state.di)


@pytest.fixture
def client(app: Starlette) -> TestClient:
    return TestClient(app)
