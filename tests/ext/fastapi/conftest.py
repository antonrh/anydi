import typing as t

import fastapi
import pytest
from starlette.testclient import TestClient

import initdi

from .app import app as _app


@pytest.fixture(scope="session")
def app() -> fastapi.FastAPI:
    return _app


@pytest.fixture(scope="session")
def di(app: fastapi.FastAPI) -> initdi.InitDI:
    return t.cast(initdi.InitDI, app.state.di)


@pytest.fixture
def client(app: fastapi.FastAPI) -> TestClient:
    return TestClient(app)
