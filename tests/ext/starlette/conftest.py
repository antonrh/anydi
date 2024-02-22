import typing as t

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

import pyxdi

from .app import app as _app


@pytest.fixture(scope="session")
def app() -> Starlette:
    return _app


@pytest.fixture(scope="session")
def di(app: Starlette) -> pyxdi.PyxDI:
    return t.cast(pyxdi.PyxDI, app.state.di)


@pytest.fixture
def client(app: Starlette) -> TestClient:
    return TestClient(app)
