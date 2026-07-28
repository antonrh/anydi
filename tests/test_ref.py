from collections.abc import AsyncIterator, Iterator
from typing import Annotated, Any
from unittest import mock

import pytest

from anydi import Container, Inject, provided
from anydi._ref import Ref


class Database:
    def __init__(self, dsn: str = "postgres://localhost") -> None:
        self.dsn = dsn
        self.queries: list[str] = []
        self.closed = False
        self.connected = False

    def execute(self, query: str) -> str:
        self.queries.append(query)
        return f"executed: {query}"

    def __len__(self) -> int:
        return len(self.queries)

    def __getitem__(self, index: int) -> str:
        return self.queries[index]


@pytest.fixture
def container() -> Container:
    return Container()


class TestRefLaziness:
    def test_ref_does_not_resolve_until_accessed(self, container: Container) -> None:
        calls: list[int] = []

        @container.provider(scope="singleton")
        def get_db() -> Database:
            calls.append(1)
            return Database()

        db = container.ref(Database)

        assert not calls

        assert db.dsn == "postgres://localhost"
        assert len(calls) == 1

    def test_ref_created_before_provider_registered(self, container: Container) -> None:
        db = container.ref(Database)

        @container.provider(scope="singleton")
        def get_db() -> Database:
            return Database(dsn="postgres://late")

        assert db.dsn == "postgres://late"

    def test_ref_repr_does_not_resolve(self, container: Container) -> None:
        calls: list[int] = []

        @container.provider(scope="singleton")
        def get_db() -> Database:
            calls.append(1)
            return Database()

        db = container.ref(Database)

        assert repr(db) == "<Ref for tests.test_ref.Database>"
        assert not calls

    def test_ref_unregistered_dependency(self, container: Container) -> None:
        db = container.ref(Database)

        with pytest.raises(LookupError, match="is either not registered"):
            _ = db.dsn

    def test_ref_transient_provider_rejected(self, container: Container) -> None:
        container.register(Database, lambda: Database(), scope="transient")

        with pytest.raises(TypeError, match="has a `transient` scope"):
            container.ref(Database)

    def test_ref_transient_named_dependency_rejected(
        self, container: Container
    ) -> None:
        container.register(
            Annotated[Database, "temp"], lambda: Database(), scope="transient"
        )

        with pytest.raises(TypeError, match="has a `transient` scope"):
            container.ref(Annotated[Database, "temp"])

    def test_ref_transient_provided_class_rejected(self, container: Container) -> None:
        @provided(scope="transient")
        class Tracker:
            pass

        with pytest.raises(TypeError, match="has a `transient` scope"):
            container.ref(Tracker)

    def test_ref_transient_provider_rejected_on_build(
        self, container: Container
    ) -> None:
        container.ref(Database)

        container.register(Database, lambda: Database(), scope="transient")

        with pytest.raises(TypeError, match="has a `transient` scope"):
            container.build()

    def test_ref_async_provider_rejected(self, container: Container) -> None:
        @container.provider(scope="singleton")
        async def get_db() -> Database:
            return Database()

        with pytest.raises(TypeError, match="cannot be resolved in synchronous mode"):
            container.ref(Database)

    def test_ref_async_dependency_rejected(self, container: Container) -> None:
        class Connection:
            pass

        @container.provider(scope="singleton")
        async def get_connection() -> Connection:
            return Connection()

        @container.provider(scope="singleton")
        def get_db(connection: Connection) -> Database:
            return Database()

        with pytest.raises(TypeError, match="cannot be resolved in synchronous mode"):
            container.ref(Database)

    def test_ref_async_provider_rejected_on_build(self, container: Container) -> None:
        db = container.ref(Database)

        @container.provider(scope="singleton")
        async def get_db() -> Database:
            return Database()

        with pytest.raises(TypeError, match="cannot be resolved in synchronous mode"):
            container.build()

        assert repr(db) == "<Ref for tests.test_ref.Database>"

    async def test_ref_async_singleton_resource_allowed(
        self, container: Container
    ) -> None:
        @container.provider(scope="singleton")
        async def get_db() -> AsyncIterator[Database]:
            db = Database()
            yield db
            db.closed = True

        db = container.ref(Database)

        # The instance is only available once `astart()` has created the resource
        with pytest.raises(TypeError, match="cannot be created in synchronous mode"):
            _ = db.dsn

        async with container:
            assert db.dsn == "postgres://localhost"

    async def test_ref_with_async_lifespan_resource(self, container: Container) -> None:
        @container.provider(scope="singleton")
        def get_db() -> Database:
            return Database()

        @container.provider(scope="singleton")
        async def db_lifespan(db: Database) -> AsyncIterator[None]:
            db.connected = True
            yield
            db.connected = False

        db = container.ref(Database)

        async with container:
            assert db.connected is True

        assert db.connected is False

    async def test_ref_async_request_resource_rejected(
        self, container: Container
    ) -> None:
        @container.provider(scope="request")
        async def get_db() -> AsyncIterator[Database]:
            yield Database()

        with pytest.raises(TypeError, match="cannot be resolved in synchronous mode"):
            container.ref(Database)


class TestRefProxying:
    def test_ref_proxies_attributes_and_methods(self, container: Container) -> None:
        container.register(Database, lambda: Database(), scope="singleton")

        db = container.ref(Database)

        assert db.execute("select 1") == "executed: select 1"
        assert db.queries == ["select 1"]
        assert len(db) == 1
        assert db[0] == "select 1"
        assert bool(db) is True

    def test_ref_proxies_isinstance_and_class(self, container: Container) -> None:
        container.register(Database, lambda: Database(), scope="singleton")

        db = container.ref(Database)

        assert isinstance(db, Database)
        assert db.__class__ is Database

    def test_ref_setattr_writes_through(self, container: Container) -> None:
        container.register(Database, lambda: Database(), scope="singleton")

        db = container.ref(Database)
        db.dsn = "postgres://updated"

        assert container.resolve(Database).dsn == "postgres://updated"

    def test_ref_annotated_dependency(self, container: Container) -> None:
        container.register(
            Annotated[str, "dsn"], lambda: "postgres://annotated", scope="singleton"
        )

        dsn = container.ref(Annotated[str, "dsn"])

        assert dsn.upper() == "POSTGRES://ANNOTATED"

    def test_ref_named_dependencies_do_not_collide(self, container: Container) -> None:
        container.register(
            Annotated[Database, "primary"],
            lambda: Database(dsn="postgres://primary"),
            scope="singleton",
        )
        container.register(
            Annotated[Database, "replica"],
            lambda: Database(dsn="postgres://replica"),
            scope="singleton",
        )

        primary = container.ref(Annotated[Database, "primary"])
        replica = container.ref(Annotated[Database, "replica"])

        assert primary.dsn == "postgres://primary"
        assert replica.dsn == "postgres://replica"

    def test_ref_provided_class(self, container: Container) -> None:
        @provided(scope="singleton")
        class Service:
            name = "service"

        service = container.ref(Service)

        assert service.name == "service"

    def test_ref_from_context_dependency(self, container: Container) -> None:
        container.register(Database, scope="request", from_context=True)

        db = container.ref(Database)

        with container.request_context() as context:
            context.set(Database, Database(dsn="postgres://first"))
            assert db.dsn == "postgres://first"

        with container.request_context() as context:
            context.set(Database, Database(dsn="postgres://second"))
            assert db.dsn == "postgres://second"

    def test_ref_alias(self, container: Container) -> None:
        class SqlDatabase(Database):
            pass

        container.register(SqlDatabase, scope="singleton", alias=Database)

        db = container.ref(Database)

        assert isinstance(db, SqlDatabase)


class TestRefCaching:
    def _spy(self, container: Container) -> Any:
        return mock.patch.object(
            container, "resolve", wraps=container.resolve, autospec=True
        )

    def test_ref_caches_singleton(self, container: Container) -> None:
        container.register(Database, lambda: Database(), scope="singleton")

        db = container.ref(Database)

        with self._spy(container) as resolve:
            assert db.dsn
            assert db.dsn
            assert db.dsn

        assert resolve.call_count == 1

    def test_ref_without_cache_resolves_every_access(
        self, container: Container
    ) -> None:
        container.register(Database, lambda: Database(), scope="singleton")

        db = container.ref(Database, cache=False)

        with self._spy(container) as resolve:
            assert db.dsn
            assert db.dsn

        assert resolve.call_count == 2

    def test_ref_does_not_cache_request_scoped(self, container: Container) -> None:
        counter = iter(range(100))

        @container.provider(scope="request")
        def get_db() -> Database:
            return Database(dsn=f"postgres://{next(counter)}")

        db = container.ref(Database)

        with container.request_context():
            assert db.dsn == "postgres://0"
            assert db.dsn == "postgres://0"

        with container.request_context():
            assert db.dsn == "postgres://1"

    def test_ref_request_scoped_outside_context(self, container: Container) -> None:
        @container.provider(scope="request")
        def get_db() -> Database:
            return Database()

        db = container.ref(Database)

        with pytest.raises(LookupError, match="request context has not been started"):
            _ = db.dsn


class TestRefInvalidation:
    def test_ref_picks_up_override(self, container: Container) -> None:
        container.register(Database, lambda: Database(), scope="singleton")

        db = container.ref(Database)

        with container.test_mode():
            assert db.dsn == "postgres://localhost"

            db_mock = mock.MagicMock(spec=Database)

            with container.override(Database, db_mock):
                db.execute("delete * from users")

            db_mock.execute.assert_called_once_with("delete * from users")

            # The original instance is restored once the override is released.
            assert db.dsn == "postgres://localhost"
            assert db.queries == []

    def test_ref_picks_up_override_of_named_dependency(
        self, container: Container
    ) -> None:
        container.register(
            Annotated[Database, "primary"],
            lambda: Database(dsn="postgres://primary"),
            scope="singleton",
        )
        container.register(
            Annotated[Database, "replica"],
            lambda: Database(dsn="postgres://replica"),
            scope="singleton",
        )

        primary = container.ref(Annotated[Database, "primary"])
        replica = container.ref(Annotated[Database, "replica"])

        with container.test_mode():
            db_mock = mock.MagicMock(spec=Database)

            with container.override(Annotated[Database, "primary"], db_mock):
                primary.execute("select 1")
                # The other name keeps its own instance
                assert replica.dsn == "postgres://replica"

            db_mock.execute.assert_called_once_with("select 1")

            assert primary.dsn == "postgres://primary"

    def test_ref_picks_up_override_of_alias(self, container: Container) -> None:
        class SqlDatabase(Database):
            pass

        container.register(SqlDatabase, scope="singleton", alias=Database)

        db = container.ref(Database)

        with container.test_mode():
            assert isinstance(db, SqlDatabase)

            db_mock = mock.MagicMock(spec=Database)

            with container.override(SqlDatabase, db_mock):
                db.execute("select 1")

            db_mock.execute.assert_called_once_with("select 1")

    def test_ref_picks_up_reregistered_provider(self, container: Container) -> None:
        container.register(Database, lambda: Database(), scope="singleton")

        db = container.ref(Database)

        assert db.dsn == "postgres://localhost"

        container.register(
            Database, lambda: Database(dsn="postgres://replaced"), override=True
        )
        # The already resolved singleton is kept by the container until released
        container.release(Database)

        assert db.dsn == "postgres://replaced"

    def test_ref_invalidated_by_reset(self, container: Container) -> None:
        counter = iter(range(100))

        @container.provider(scope="singleton")
        def get_db() -> Database:
            return Database(dsn=f"postgres://{next(counter)}")

        db = container.ref(Database)

        assert db.dsn == "postgres://0"

        container.reset()

        assert db.dsn == "postgres://1"

    def test_ref_invalidated_by_release(self, container: Container) -> None:
        counter = iter(range(100))

        @container.provider(scope="singleton")
        def get_db() -> Database:
            return Database(dsn=f"postgres://{next(counter)}")

        db = container.ref(Database)

        assert db.dsn == "postgres://0"

        container.release(Database)

        assert db.dsn == "postgres://1"

    def test_ref_reflects_resolve_after_close(self, container: Container) -> None:
        @container.provider(scope="singleton")
        def get_db() -> Iterator[Database]:
            db = Database()
            yield db
            db.closed = True

        db = container.ref(Database)

        with container:
            assert db.dsn == "postgres://localhost"

        # Closing finalizes the resource, but the container keeps the instance
        assert db.closed is True
        assert db == container.resolve(Database)


class TestRefUsage:
    def test_ref_used_by_module_level_handler(self, container: Container) -> None:
        container.register(Database, lambda: Database(), scope="singleton")

        db = container.ref(Database)

        def handler() -> None:
            db.execute("delete * from users")

        with container.test_mode():
            db_mock = mock.MagicMock(spec=Database)

            with container.override(Database, db_mock):
                handler()

            db_mock.execute.assert_called_once_with("delete * from users")

    def test_ref_passed_as_injected_dependency(self, container: Container) -> None:
        container.register(Database, lambda: Database(), scope="singleton")

        @container.inject
        def handler(db: Database = Inject()) -> str:
            return db.dsn

        assert handler() == "postgres://localhost"
        assert container.ref(Database).dsn == handler()

    def test_ref_is_ref_instance(self, container: Container) -> None:
        db = container.ref(Database)

        assert type(db) is Ref
