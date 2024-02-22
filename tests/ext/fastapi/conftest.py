import typing as t

import fastapi
import pytest
from starlette.testclient import TestClient

import pyxdi

from .app import app as _app


@pytest.fixture(scope="session")
def app() -> fastapi.FastAPI:
    return _app


@pytest.fixture(scope="session")
def di(app: fastapi.FastAPI) -> pyxdi.PyxDI:
    return t.cast(pyxdi.PyxDI, app.state.di)


@pytest.fixture
def client(app: fastapi.FastAPI) -> TestClient:
    return TestClient(app)
