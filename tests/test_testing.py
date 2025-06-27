import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from typing import Annotated
from unittest import mock

import pytest

from anydi import Container, auto, singleton
from anydi.testing import TestContainer

from tests.fixtures import Service


class TestTestContainer:
    def test_from_container(self) -> None:
        container = Container()
        container.register(str, lambda: "Hello, world!", scope="singleton")

        test_container = TestContainer.from_container(container)

        assert test_container.providers == container.providers
        assert test_container.default_scope == container.default_scope

        assert test_container.resolve(str) == "Hello, world!"

    def test_override_instance(self) -> None:
        origin_name = "origin"
        overridden_name = "overridden"

        container = TestContainer()

        @container.provider(scope="singleton")
        def name() -> str:
            return origin_name

        with container.override(str, overridden_name):
            assert container.resolve(str) == overridden_name

        assert container.resolve(str) == origin_name

    def test_override_instance_provider_not_registered_using_strict_mode(self) -> None:
        container = TestContainer()

        with pytest.raises(
            LookupError, match="The provider interface `str` not registered."
        ):
            with container.override(str, "test"):
                pass

    def test_override_instance_transient_provider(self) -> None:
        overridden_uuid = uuid.uuid4()

        container = TestContainer()

        @container.provider(scope="transient")
        def uuid_provider() -> uuid.UUID:
            return uuid.uuid4()

        with container.override(uuid.UUID, overridden_uuid):
            assert container.resolve(uuid.UUID) == overridden_uuid

        assert container.resolve(uuid.UUID) != overridden_uuid

    def test_override_instance_resource_provider(self) -> None:
        origin = "origin"
        overridden = "overridden"

        container = TestContainer()

        @container.provider(scope="singleton")
        def message() -> Iterator[str]:
            yield origin

        with container.override(str, overridden):
            assert container.resolve(str) == overridden

        assert container.resolve(str) == origin

    async def test_override_instance_async_resource_provider(self) -> None:
        origin = "origin"
        overridden = "overridden"

        container = TestContainer()

        @container.provider(scope="singleton")
        async def message() -> AsyncIterator[str]:
            yield origin

        with container.override(str, overridden):
            assert (await container.aresolve(str)) == overridden

    def test_override_registered_instance(self) -> None:
        container = TestContainer()
        container.register(Annotated[str, "param"], lambda: "param", scope="singleton")

        class UserRepo:
            def get_user(self) -> str:
                return "user"

        @singleton
        class UserService:
            def __init__(self, repo: UserRepo, param: Annotated[str, "param"]) -> None:
                self.repo = repo
                self.param = param

            def process(self) -> dict[str, str]:
                return {
                    "user": self.repo.get_user(),
                    "param": self.param,
                }

        user_repo_mock = mock.MagicMock(spec=UserRepo)
        user_repo_mock.get_user.return_value = "mocked_user"

        user_service = container.resolve(UserService)

        with (
            container.override(UserRepo, user_repo_mock),
            container.override(Annotated[str, "param"], "mock"),
        ):
            assert user_service.process() == {
                "user": "mocked_user",
                "param": "mock",
            }

    async def test_override_instance_async_resolved(self) -> None:
        container = TestContainer()
        container.register(Annotated[str, "param"], lambda: "param", scope="singleton")

        @singleton
        class UserService:
            def __init__(self, param: Annotated[str, "param"]) -> None:
                self.param = param

            def process(self) -> dict[str, str]:
                return {
                    "param": self.param,
                }

        user_service = await container.aresolve(UserService)

        with container.override(Annotated[str, "param"], "mock"):
            assert user_service.process() == {
                "param": "mock",
            }

    def test_override_instance_in_strict_mode(self) -> None:
        container = TestContainer()

        class Settings:
            def __init__(self, name: str) -> None:
                self.name = name

        @container.provider(scope="singleton")
        def provide_settings() -> Settings:
            return Settings(name="test")

        @container.provider(scope="singleton")
        def provide_service(settings: Settings) -> Service:
            return Service(ident=settings.name)

        service = container.resolve(Service)

        assert service.ident == "test"

    def test_override_instance_first(self) -> None:
        container = TestContainer()

        @dataclass
        class Item:
            name: str

        class ItemRepository:
            def __init__(self, items: list[Item]) -> None:
                self.items = items

            def all(self) -> list[Item]:
                return self.items

        class ItemService:
            def __init__(self, repo: ItemRepository) -> None:
                self.repo = repo

            def get_items(self) -> list[Item]:
                return self.repo.all()

        @container.provider(scope="singleton")
        def provide_repo() -> ItemRepository:
            return ItemRepository(items=[])

        @container.provider(scope="singleton")
        def provide_service(repo: ItemRepository) -> ItemService:
            return ItemService(repo=repo)

        @container.inject
        def handler(service: ItemService = auto) -> list[Item]:
            return service.get_items()

        repo_mock = mock.MagicMock(spec=ItemRepository)
        repo_mock.all.return_value = [Item(name="mocked")]

        with container.override(ItemRepository, repo_mock):
            items = handler()

            assert items == [Item(name="mocked")]

        service = container.resolve(ItemService)

        assert service.get_items() == []

    def test_override_prop(self) -> None:
        class ServiceWithProp:
            def __init__(self, name: str = "origin") -> None:
                self.name = name

        container = TestContainer()

        service = container.resolve(ServiceWithProp)

        assert service.name == "origin"
