import pytest
import typer
from typer.testing import CliRunner

from anydi import Container

from .app import app as _app, container as _container


@pytest.fixture(scope="session")
def app() -> typer.Typer:
    return _app


@pytest.fixture(scope="session")
def container() -> Container:
    return _container


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()
