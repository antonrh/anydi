import typing as t

import pytest
from flask.testing import FlaskClient

import pyxdi


@pytest.fixture(scope="module", autouse=True)
def init_di() -> t.Iterator[None]:
    pyxdi.close()  # ensure that pyxdi closed
    yield


@pytest.fixture(scope="module")
def client() -> t.Iterator[FlaskClient]:
    from examples.flask import app

    with app.test_client() as client:
        yield client


def test_create_user(client: FlaskClient) -> None:
    response = client.post("/users", json={"email": "user@mail.com"})

    assert response.status_code == 200
    assert response.json["email"] == "user@mail.com"  # type: ignore[index]
