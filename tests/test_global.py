from collections.abc import Iterator
from unittest import mock

import pytest

from anydi import (
    Container,
    _global,
    create_global_container,
    get_global_container,
    get_global_container_or_none,
    global_ref,
    reset_global_container,
    set_global_container,
)
from anydi._global import GlobalRef

from tests.fixtures import Service


@pytest.fixture(autouse=True)
def _clean_global_state() -> Iterator[None]:
    """Keep the process-wide container and references out of other tests."""
    reset_global_container()
    _global._refs.clear()
    yield
    reset_global_container()
    _global._refs.clear()


class TestGlobalContainer:
    def test_create_global_container(self) -> None:
        container = create_global_container()

        assert isinstance(container, Container)
        assert get_global_container() is container

    def test_create_global_container_with_providers(self) -> None:
        container = create_global_container()
        container.register(str, lambda: "test", scope="singleton")

        assert container.resolve(str) == "test"

    def test_create_global_container_twice(self) -> None:
        create_global_container()

        with pytest.raises(RuntimeError, match="already set"):
            create_global_container()

    def test_set_global_container(self) -> None:
        container = Container()

        set_global_container(container)

        assert get_global_container() is container

    def test_set_global_container_same_twice(self) -> None:
        container = Container()

        set_global_container(container)
        set_global_container(container)

        assert get_global_container() is container

    def test_set_global_container_replace(self) -> None:
        set_global_container(Container())

        with pytest.raises(RuntimeError, match="already set"):
            set_global_container(Container())

    def test_get_global_container_not_set(self) -> None:
        with pytest.raises(RuntimeError, match="is not set"):
            get_global_container()

    def test_get_global_container_or_none(self) -> None:
        assert get_global_container_or_none() is None

        container = create_global_container()

        assert get_global_container_or_none() is container

    def test_reset_global_container(self) -> None:
        create_global_container()

        reset_global_container()

        with pytest.raises(RuntimeError, match="is not set"):
            get_global_container()


class TestGlobalRef:
    def test_global_ref_created_before_container(self) -> None:
        service = global_ref(Service)

        container = create_global_container()
        container.register(Service, lambda: Service(ident="global"), scope="singleton")

        assert service.ident == "global"

    def test_global_ref_created_after_container(self) -> None:
        container = create_global_container()
        container.register(Service, lambda: Service(ident="global"), scope="singleton")

        service = global_ref(Service)

        assert service.ident == "global"

    def test_global_ref_without_container(self) -> None:
        service = global_ref(Service)

        with pytest.raises(
            RuntimeError, match=r"Cannot resolve `tests\.fixtures\.Service`"
        ):
            _ = service.ident

    def test_global_ref_repr(self) -> None:
        service = global_ref(Service)

        assert repr(service) == "<GlobalRef for tests.fixtures.Service, unbound>"

        container = create_global_container()
        container.register(Service, lambda: Service(ident="global"), scope="singleton")
        _ = service.ident

        assert repr(service) == "<GlobalRef for tests.fixtures.Service>"

    def test_global_ref_unregistered_dependency(self) -> None:
        service = global_ref(Service)

        create_global_container()

        with pytest.raises(LookupError, match="is either not registered"):
            _ = service.ident

    def test_global_ref_rebinds_after_reset(self) -> None:
        service = global_ref(Service)

        first = create_global_container()
        first.register(Service, lambda: Service(ident="first"), scope="singleton")

        assert service.ident == "first"

        reset_global_container()

        second = create_global_container()
        second.register(Service, lambda: Service(ident="second"), scope="singleton")

        assert service.ident == "second"

    def test_global_ref_picks_up_override(self) -> None:
        container = create_global_container()
        container.register(Service, lambda: Service(ident="global"), scope="singleton")

        service = global_ref(Service)

        with container.test_mode():
            service_mock = mock.Mock(spec=Service)
            service_mock.ident = "overridden"

            with container.override(Service, service_mock):
                assert service.ident == "overridden"

            assert service.ident == "global"

    def test_global_ref_is_global_ref_instance(self) -> None:
        assert type(global_ref(Service)) is GlobalRef


class TestGlobalRefValidation:
    def test_transient_rejected_on_access(self) -> None:
        container = create_global_container()
        container.register(Service, lambda: Service(ident="global"), scope="transient")

        # Creating the reference is allowed, the container may change later
        service = global_ref(Service)

        with pytest.raises(TypeError, match="has a `transient` scope"):
            _ = service.ident

    def test_transient_rejected_on_build(self) -> None:
        global_ref(Service)

        container = create_global_container()
        container.register(Service, lambda: Service(ident="global"), scope="transient")

        with pytest.raises(TypeError, match="has a `transient` scope"):
            container.build()

    def test_async_provider_rejected_on_access(self) -> None:
        container = create_global_container()

        @container.provider(scope="singleton")
        async def get_service() -> Service:
            return Service(ident="global")

        service = global_ref(Service)

        with pytest.raises(TypeError, match="cannot be resolved in synchronous mode"):
            _ = service.ident
