import typing as t
from dataclasses import asdict

from flask import Flask, abort, jsonify, request

import pyxdi.ext.flask
from examples.common.repository import InMemoryUserRepository, UserRepository
from examples.common.service import UserService

app = Flask(__name__)

pyxdi.init()
pyxdi.ext.flask.install(app)


@pyxdi.provider
def user_repository() -> UserRepository:
    return InMemoryUserRepository()


@pyxdi.provider
def user_service(user_repository: UserRepository) -> UserService:
    return UserService(repository=user_repository)


@app.get("/users")
@pyxdi.inject
def get_users(user_service: UserService = pyxdi.dep) -> t.Any:
    users = user_service.get_users()
    return jsonify([asdict(user) for user in users])


@app.post("/users")
@pyxdi.inject
def create_user(user_service: UserService = pyxdi.dep) -> t.Any:
    data = request.json or {}
    user = user_service.create_user(email=data.get("email", ""))
    return jsonify(asdict(user))


@app.get("/users/<user_id>")
@pyxdi.inject
def get_user(user_id: str, user_service: UserService = pyxdi.dep) -> t.Any:
    user = user_service.get_user(user_id=user_id)
    if not user:
        abort(404)
    return jsonify(asdict(user))


if __name__ == "__main__":
    app.run(port=5555, debug=True)
