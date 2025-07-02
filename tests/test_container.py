import asyncio
import sys
import threading
import uuid
from collections.abc import AsyncIterator, Iterator, Sequence
from dataclasses import dataclass
from typing import Annotated, Any, Callable, Union

import pytest
from typing_extensions import Self

from anydi import Container, Provider, Scope, auto, request, singleton, transient
from anydi._provider import ProviderKind
from anydi._typing import Event

from tests.fixtures import (
    Class,
    Resource,
    Service,
    UniqueId,
    async_event,
    async_generator,
    coro,
    event,
    func,
    generator,
    iterator,
)


@pytest.fixture
def container() -> Container:
    return Container()


class TestContainer:
    def test_register_provider(self, container: Container) -> None:
        def provider_call() -> str:
            return "test"

        provider = container.register(str, provider_call, scope="transient")

        assert provider.call == provider_call
        assert provider.scope == "transient"

    def test_provider_decorator(self, container: Container) -> None:
        @container.provider(scope="singleton")
        def ident() -> str:
            return "1000"

        provider = container.providers[str]

        assert provider.call == ident
        assert provider.scope == "singleton"
        assert provider.interface is str

    @pytest.mark.parametrize(
        ("call", "kind", "interface"),
        [
            (func, ProviderKind.FUNCTION, str),
            (Class, ProviderKind.CLASS, Class),
            (generator, ProviderKind.GENERATOR, str),
            (async_generator, ProviderKind.ASYNC_GENERATOR, str),
            (coro, ProviderKind.COROUTINE, str),
        ],
    )
    def test_register_provider_different_kind(
        self,
        container: Container,
        call: Callable[..., Any],
        kind: ProviderKind,
        interface: Any,
    ) -> None:
        provider = container._register_provider(call, "singleton")

        assert provider.kind == kind
        assert provider.interface is interface

    @pytest.mark.parametrize(
        ("annotation", "expected"),
        [
            (str, str),
            (int, int),
            (Service, Service),
            (Iterator[Service], Service),
            (AsyncIterator[Service], Service),
            (dict[str, Any], dict[str, Any]),
            (list[str], list[str]),
            ("list[str]", list[str]),
            (tuple[str, ...], tuple[str, ...]),
            ("tuple[str, ...]", tuple[str, ...]),
            ('Annotated[str, "name"]', Annotated[str, "name"]),
        ],
    )
    def test_register_provider_interface(
        self, container: Container, annotation: type[Any], expected: type[Any]
    ) -> None:
        def call() -> annotation:  # type: ignore[valid-type]
            return object()

        provider = container._register_provider(call, "singleton")

        assert provider.interface == expected

    @pytest.mark.parametrize(
        ("call", "kind"),
        [
            (event, ProviderKind.GENERATOR),
            (async_event, ProviderKind.ASYNC_GENERATOR),
        ],
    )
    def test_register_provider_event(
        self,
        container: Container,
        call: Callable[..., Any],
        kind: ProviderKind,
    ) -> None:
        provider = container._register_provider(call, "singleton")

        assert provider.kind == kind
        assert issubclass(provider.interface, Event)

    def test_register_provider_with_interface(self, container: Container) -> None:
        provider = container._register_provider(lambda: "hello", "singleton", str)

        assert provider.interface is str

    def test_register_provider_with_none(self, container: Container) -> None:
        with pytest.raises(
            TypeError, match="Missing `(.*?)` provider return annotation."
        ):
            container._register_provider(lambda: "hello", "singleton", None)

    def test_register_provider_provider_without_return_annotation(
        self, container: Container
    ) -> None:
        def provide_message():  # type: ignore[no-untyped-def]
            return "hello"

        with pytest.raises(
            TypeError, match="Missing `(.*?)` provider return annotation."
        ):
            container._register_provider(provide_message, "singleton")

    def test_register_provider_not_callable(self, container: Container) -> None:
        with pytest.raises(
            TypeError,
            match="The provider `Test` is invalid because it is not a callable object.",
        ):
            container._register_provider("Test", "singleton")  # type: ignore[arg-type]

    def test_register_provider_iterator_no_arg_not_allowed(
        self, container: Container
    ) -> None:
        with pytest.raises(
            TypeError,
            match=(
                "Cannot use `(.*?)` resource type annotation "
                "without actual type argument."
            ),
        ):
            container._register_provider(iterator, "singleton")

    def test_register_provider_unsupported_scope(self, container: Container) -> None:
        with pytest.raises(
            ValueError,
            match=(
                "The provider `(.*?)` scope is invalid. Only the following scopes "
                "are supported: transient, singleton, request. "
                "Please use one of the supported scopes when registering a provider."
            ),
        ):
            container._register_provider(generator, "other")  # type: ignore[arg-type]

    def test_register_provider_transient_resource_not_allowed(
        self, container: Container
    ) -> None:
        with pytest.raises(
            TypeError,
            match=(
                "The resource provider `(.*?)` is attempting to "
                "register with a transient scope, which is not allowed."
            ),
        ):
            container._register_provider(generator, "transient")

    def test_register_provider_without_annotation(self, container: Container) -> None:
        def service_ident() -> str:
            return "10000"

        def service(ident) -> Service:  # type: ignore[no-untyped-def]
            return Service(ident=ident)

        with pytest.raises(
            TypeError, match="Missing provider `(.*?)` dependency `ident` annotation."
        ):
            container._register_provider(service, "singleton")

    def test_register_provider_positional_only_parameter_not_allowed(
        self, container: Container
    ) -> None:
        def provider_message(a: int, /, b: str) -> str:
            return f"{a} {b}"

        with pytest.raises(
            TypeError,
            match="Positional-only parameters are not allowed in the provider `(.*?)`.",
        ):
            container._register_provider(provider_message, "singleton")

    def test_register_provider_already_registered(self, container: Container) -> None:
        container.register(str, lambda: "test", scope="singleton")

        with pytest.raises(
            LookupError, match="The provider interface `str` already registered."
        ):
            container.register(str, lambda: "other", scope="singleton")

    def test_register_provider_override(self, container: Container) -> None:
        container.register(str, lambda: "old", scope="singleton")

        def new_provider_call() -> str:
            return "new"

        provider = container.register(
            str, new_provider_call, scope="singleton", override=True
        )

        assert provider.call == new_provider_call

    def test_register_provider_named(self, container: Container) -> None:
        container.register(
            Annotated[str, "msg1"],
            lambda: "test1",
            scope="singleton",
        )
        container.register(
            Annotated[str, "msg2"],
            lambda: "test2",
            scope="singleton",
        )

        assert container.is_registered(Annotated[str, "msg1"])
        assert container.is_registered(Annotated[str, "msg2"])

    def test_register_providers_via_constructor(self) -> None:
        container = Container(
            providers=[
                Provider(call=lambda: "test", scope="singleton", interface=str),
                Provider(call=lambda: 1, scope="singleton", interface=int),
            ]
        )

        assert container.is_registered(str)
        assert container.is_registered(int)

    def test_register_provider_invalid_transient_resource(
        self, container: Container
    ) -> None:
        def provider_call() -> Iterator[str]:
            yield "test"

        with pytest.raises(
            TypeError,
            match=(
                "The resource provider `(.*?)` is attempting to register "
                "with a transient scope, which is not allowed."
            ),
        ):
            container.register(str, provider_call, scope="transient")

    def test_register_provider_invalid_transient_async_resource(
        self,
        container: Container,
    ) -> None:
        async def provider_call() -> AsyncIterator[str]:
            yield "test"

        with pytest.raises(
            TypeError,
            match=(
                "The resource provider `(.*?)` is attempting to register with a "
                "transient scope, which is not allowed."
            ),
        ):
            container.register(str, provider_call, scope="transient")

    def test_register_provider_valid_resource(self, container: Container) -> None:
        def provider_call1() -> Iterator[str]:
            yield "test"

        def provider_call2() -> Iterator[int]:
            yield 100

        container.register(str, provider_call1, scope="singleton")
        container.register(int, provider_call2, scope="request")

    def test_register_provider_valid_async_resource(self, container: Container) -> None:
        async def provider_call1() -> AsyncIterator[str]:
            yield "test"

        async def provider_call2() -> AsyncIterator[int]:
            yield 100

        container.register(str, provider_call1, scope="singleton")
        container.register(int, provider_call2, scope="request")

    def test_register_invalid_provider_type(self, container: Container) -> None:
        with pytest.raises(
            TypeError,
            match="The provider `Test` is invalid because it is not a callable object.",
        ):
            container.register(str, "Test", scope="singleton")  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("scope1", "scope2", "scope3", "valid"),
        [
            ("transient", "transient", "transient", True),
            ("transient", "transient", "singleton", True),
            ("transient", "transient", "request", True),
            ("transient", "singleton", "transient", False),
            ("transient", "singleton", "singleton", True),
            ("transient", "singleton", "request", False),
            ("transient", "request", "transient", False),
            ("transient", "request", "singleton", True),
            ("transient", "request", "request", True),
            ("singleton", "transient", "transient", False),
            ("singleton", "transient", "singleton", False),
            ("singleton", "transient", "request", False),
            ("singleton", "singleton", "transient", False),
            ("singleton", "singleton", "singleton", True),
            ("singleton", "singleton", "request", False),
            ("singleton", "request", "transient", False),
            ("singleton", "request", "singleton", False),
            ("singleton", "request", "request", False),
            ("request", "transient", "transient", False),
            ("request", "transient", "singleton", False),
            ("request", "transient", "request", False),
            ("request", "singleton", "transient", False),
            ("request", "singleton", "singleton", True),
            ("request", "singleton", "request", False),
            ("request", "request", "transient", False),
            ("request", "request", "singleton", True),
            ("request", "request", "request", True),
        ],
    )
    def test_register_provider_match_scopes(
        self,
        container: Container,
        scope1: Scope,
        scope2: Scope,
        scope3: Scope,
        valid: bool,
    ) -> None:
        def a() -> int:
            return 2

        def b(a: int) -> float:
            return a * 2.5

        def mixed(a: int, b: float) -> str:
            return f"{a} * {b} = {a * b}"

        try:
            container.register(int, a, scope=scope3)
            container.register(float, b, scope=scope2)
            container.register(str, mixed, scope=scope1)
        except ValueError:
            result = False
        else:
            result = True

        assert result == valid

    def test_register_provider_match_scopes_error(self, container: Container) -> None:
        def provider_int() -> int:
            return 1000

        def provider_str(n: int) -> str:
            return f"{n}"

        container.register(int, provider_int, scope="request")

        with pytest.raises(
            ValueError,
            match=(
                "The provider `(.*?)` with a `singleton` scope cannot depend on "
                "`(.*?)` with a `request` scope. Please ensure all providers are "
                "registered with matching scopes."
            ),
        ):
            container.register(str, provider_str, scope="singleton")

    def test_register_provider_with_not_registered_sub_provider(
        self,
        container: Container,
    ) -> None:
        def dep2(dep1: int) -> str:
            return str(dep1)

        with pytest.raises(
            LookupError,
            match=(
                "The provider `(.*?).dep2` depends on `dep1` of type `int`, "
                "which has not been registered or set. To resolve this, "
                "ensure that `dep1` is registered before attempting to use it."
            ),
        ):
            container.register(str, dep2, scope="singleton")

    def test_register_events(self, container: Container) -> None:
        events = []

        @container.provider(scope="singleton")
        def message() -> str:
            return "test"

        @container.provider(scope="singleton")
        def event_1(message: str) -> Iterator[None]:
            events.append(f"event_1: before {message}")
            yield
            events.append(f"event_1: after {message}")

        @container.provider(scope="request")
        def event_2(message: str) -> Iterator[None]:
            events.append(f"event_2: before {message}")
            yield
            events.append(f"event_2: after {message}")

        # Ensure that non-event is not called
        @container.provider(scope="request")
        def non_event(message: str) -> Iterator[int]:
            events.append(f"non_event: before {message}")
            yield 1
            events.append(f"non_event: after {message}")

        with container, container.request_context():
            assert events == [
                "event_1: before test",
                "event_2: before test",
            ]

        assert events == [
            "event_1: before test",
            "event_2: before test",
            "event_2: after test",
            "event_1: after test",
        ]

    async def test_register_async_events(self, container: Container) -> None:
        events = []

        @container.provider(scope="singleton")
        def message() -> str:
            return "test"

        @container.provider(scope="singleton")
        async def event_1(message: str) -> AsyncIterator[None]:
            events.append(f"event_1: before {message}")
            yield
            events.append(f"event_1: after {message}")

        @container.provider(scope="request")
        def event_2(message: str) -> Iterator[None]:
            events.append(f"event_2: before {message}")
            yield
            events.append(f"event_2: after {message}")

        # Ensure that non-event is not called
        @container.provider(scope="request")
        async def non_event(message: str) -> AsyncIterator[int]:
            events.append(f"non_event: before {message}")
            yield 1
            events.append(f"non_event: after {message}")

        async with container, container.arequest_context():
            assert events == [
                "event_1: before test",
                "event_2: before test",
            ]

        assert events == [
            "event_1: before test",
            "event_2: before test",
            "event_2: after test",
            "event_1: after test",
        ]

    def test_unregister_provider(self, container: Container) -> None:
        container.register(str, lambda: "test", scope="singleton")

        assert container.is_registered(str)

        container.unregister(str)

        assert not container.is_registered(str)

    def test_unregister_provider_resource(self, container: Container) -> None:
        @container.provider(scope="singleton")
        def message() -> Iterator[str]:
            yield "test"

        assert container.is_registered(str)
        assert str in container._resources["singleton"]

        container.unregister(str)

        assert not container.is_registered(str)
        assert str not in container._resources["singleton"]

    def test_unregister_request_scoped_provider(self, container: Container) -> None:
        container.register(str, lambda: "test", scope="request")

        assert container.is_registered(str)

        container.unregister(str)

        assert not container.is_registered(str)

    def test_unregister_not_registered_provider(self, container: Container) -> None:
        with pytest.raises(
            LookupError, match="The provider interface `str` not registered."
        ):
            container.unregister(str)

    # Lifespan

    def test_start_and_close_singleton_context(self, container: Container) -> None:
        events = []

        def dep1() -> Iterator[str]:
            events.append("dep1:before")
            yield "test"
            events.append("dep1:after")

        container.register(str, dep1, scope="singleton")

        container.start()

        assert container.resolve(str) == "test"

        container.close()

        assert events == ["dep1:before", "dep1:after"]

    def test_request_context(self, container: Container) -> None:
        events = []

        def dep1() -> Iterator[str]:
            events.append("dep1:before")
            yield "test"
            events.append("dep1:after")

        container.register(str, dep1, scope="request")

        with container.request_context():
            assert container.resolve(str) == "test"

        assert events == ["dep1:before", "dep1:after"]

    # Asynchronous lifespan

    async def test_astart_and_aclose_singleton_context(
        self, container: Container
    ) -> None:
        events = []

        async def dep1() -> AsyncIterator[str]:
            events.append("dep1:before")
            yield "test"
            events.append("dep1:after")

        container.register(str, dep1, scope="singleton")

        await container.astart()

        assert container.resolve(str) == "test"

        await container.aclose()

        assert events == ["dep1:before", "dep1:after"]

    async def test_arequest_context(self, container: Container) -> None:
        events = []

        async def dep1() -> AsyncIterator[str]:
            events.append("dep1:before")
            yield "test"
            events.append("dep1:after")

        container.register(str, dep1, scope="request")

        async with container.arequest_context():
            assert await container.aresolve(str) == "test"

        assert events == ["dep1:before", "dep1:after"]

    def test_reset_resolved_instances(self, container: Container) -> None:
        container.register(str, lambda: "test", scope="singleton")
        container.register(int, lambda: 1, scope="singleton")

        container.resolve(str)
        container.resolve(int)

        assert container.is_resolved(str)
        assert container.is_resolved(int)

        container.reset()

        assert not container.is_resolved(str)
        assert not container.is_resolved(int)

    def test_reset_transient(self, container: Container) -> None:
        container.register(str, lambda: "test", scope="transient")

        _ = container.resolve(str)

        assert not container.is_resolved(str)

        container.reset()

        assert not container.is_resolved(str)

    # Instance

    def test_resolve_singleton_scoped(self, container: Container) -> None:
        instance = "test"

        container.register(str, lambda: instance, scope="singleton")

        assert container.resolve(str) == instance

    def test_resolve_singleton_scoped_not_started(self, container: Container) -> None:
        @container.provider(scope="singleton")
        def message() -> Iterator[str]:
            yield "test"

        assert container.resolve(str) == "test"

    def test_resolve_singleton_scoped_resource(self, container: Container) -> None:
        instance = "test"

        def provide() -> Iterator[str]:
            yield instance

        container.register(str, provide, scope="singleton")
        container.start()

        assert container.resolve(str) == instance

    def test_resolve_singleton_scoped_started_with_async_resource_provider(
        self,
        container: Container,
    ) -> None:
        instance = "test"

        async def provide() -> AsyncIterator[str]:
            yield instance

        container.register(str, provide, scope="singleton")

        with pytest.raises(
            TypeError,
            match=(
                "The instance for the provider `(.*?).provide` cannot be created "
                "in synchronous mode."
            ),
        ):
            container.start()

    def test_resolve_singleton_resource(self, container: Container) -> None:
        instance = "test"

        def provide() -> Iterator[str]:
            yield instance

        container.register(str, provide, scope="singleton")

        container.resolve(str)

    def test_resolve_singleton_scoped_thread_safe(self, container: Container) -> None:
        @container.provider(scope="singleton")
        def provide_unique_id() -> UniqueId:
            return UniqueId()

        unique_ids = set()

        def use_unique_id() -> None:
            unique_id = container.resolve(UniqueId)
            unique_ids.add(unique_id)

        threads = [threading.Thread(target=use_unique_id) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(unique_ids) == 1

    async def test_resolve_singleton_async_resource(self, container: Container) -> None:
        instance = "test"

        def provide() -> Iterator[str]:
            yield instance

        container.register(str, provide, scope="singleton")

        await container.astart()

        assert container.resolve(str) == instance

    async def test_resolve_singleton_async_and_sync_resources(
        self, container: Container
    ) -> None:
        instance_str = "test"
        instance_int = 100

        def provider_1() -> Iterator[str]:
            yield instance_str

        async def provider_2() -> AsyncIterator[int]:
            yield instance_int

        container.register(str, provider_1, scope="singleton")
        container.register(int, provider_2, scope="singleton")

        await container.astart()

        assert container.resolve(str) == instance_str
        assert container.resolve(int) == instance_int

    async def test_resolved_singleton_async_resource_not_started(
        self,
        container: Container,
    ) -> None:
        instance = "test"

        async def provide() -> AsyncIterator[str]:
            yield instance

        container.register(str, provide, scope="singleton")

        with pytest.raises(
            TypeError,
            match=(
                "The instance for the provider `(.*?).provide` cannot be created "
                "in synchronous mode."
            ),
        ):
            container.resolve(str)

    def test_resolve_singleton_annotated_resource(self, container: Container) -> None:
        instance = "test"

        @container.provider(scope="singleton")
        def provide() -> Iterator[Annotated[str, "message"]]:
            yield instance

        result = container.resolve(Annotated[str, "message"])

        assert result == instance

    async def test_resolve_singleton_annotated_async_resource(
        self, container: Container
    ) -> None:
        instance = "test"

        @container.provider(scope="singleton")
        async def provide() -> AsyncIterator[Annotated[str, "message"]]:
            yield instance

        result = await container.aresolve(Annotated[str, "message"])

        assert result == instance

    async def test_resolve_singleton_scoped_coro_safe(
        self, container: Container
    ) -> None:
        @container.provider(scope="singleton")
        async def provide_unique_id() -> UniqueId:
            return UniqueId()

        unique_ids = set()

        async def use_service() -> None:
            unique_id = await container.aresolve(UniqueId)
            unique_ids.add(unique_id)

        tasks = [use_service() for _ in range(10)]

        await asyncio.gather(*tasks)

        assert len(unique_ids) == 1

    async def test_resolve_scoped_coro_safe(self, container: Container) -> None:
        @container.provider(scope="request")
        async def provide_unique_id() -> UniqueId:
            return UniqueId()

        unique_ids = set()

        async def use_unique_id() -> None:
            async with container.arequest_context():
                unique_id = await container.aresolve(UniqueId)
                unique_ids.add(unique_id)

        tasks = [use_unique_id() for _ in range(10)]
        await asyncio.gather(*tasks)

        assert len(unique_ids) == 10

    def test_resolve_request_scoped(self, container: Container) -> None:
        instance = "test"

        container.register(str, lambda: instance, scope="request")

        with container.request_context():
            assert container.resolve(str) == instance

    def test_resolve_request_scoped_not_started(self, container: Container) -> None:
        instance = "test"

        container.register(str, lambda: instance, scope="request")

        with pytest.raises(
            LookupError,
            match=(
                "The request context has not been started. Please ensure that the "
                "request context is properly initialized before attempting to use it."
            ),
        ):
            container.resolve(str)

    def test_resolve_request_scoped_annotated_resource(
        self, container: Container
    ) -> None:
        instance = "test"

        @container.provider(scope="request")
        def provide() -> Iterator[Annotated[str, "message"]]:
            yield instance

        with container.request_context():
            result = container.resolve(Annotated[str, "message"])

        assert result == instance

    async def test_resolve_request_scoped_annotated_async_resource(
        self,
        container: Container,
    ) -> None:
        instance = "test"

        @container.provider(scope="request")
        async def provide() -> AsyncIterator[Annotated[str, "message"]]:
            yield instance

        async with container.arequest_context():
            result = await container.aresolve(Annotated[str, "message"])

        assert result == instance

    def test_resolve_request_scoped_unresolved_yet(self, container: Container) -> None:
        class Request:
            def __init__(self, path: str) -> None:
                self.path = path

        @container.provider(scope="request")
        def req_path(req: Request) -> str:
            return req.path

        with container.request_context() as context:
            context.set(Request, Request(path="test"))
            assert container.resolve(str) == "test"

    def test_resolve_request_scoped_unresolved_error(
        self, container: Container
    ) -> None:
        class Request:
            def __init__(self, path: str) -> None:
                self.path = path

        @container.provider(scope="request")
        def req_path(req: Request) -> str:
            return req.path

        with (
            pytest.raises(
                LookupError,
                match=(
                    "You are attempting to get the parameter `req` with the annotation "
                    "`(.*?).Request` as a dependency into `(.*?).req_path` which is "
                    "not registered or set in the scoped context."
                ),
            ),
            container.request_context(),
        ):
            container.resolve(str)

    def test_resolve_scoped_thread_safe(self, container: Container) -> None:
        @container.provider(scope="request")
        def provide_unique_id() -> UniqueId:
            return UniqueId()

        unique_ids = set()

        def use_unique_id() -> None:
            with container.request_context():
                unique_id = container.resolve(UniqueId)
                unique_ids.add(unique_id)

        threads = [threading.Thread(target=use_unique_id) for n in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(unique_ids) == 10

    def test_resolve_transient_scoped(self, container: Container) -> None:
        container.register(uuid.UUID, uuid.uuid4, scope="transient")

        assert container.resolve(uuid.UUID) != container.resolve(uuid.UUID)

    def test_sync_resolve_transient_async_provider(self, container: Container) -> None:
        @container.provider(scope="transient")
        async def get_uuid() -> uuid.UUID:
            return uuid.uuid4()

        with pytest.raises(
            TypeError,
            match=(
                "The instance for the provider `(.*?).get_uuid` cannot "
                "be created in synchronous mode."
            ),
        ):
            container.resolve(uuid.UUID)

    async def test_async_resolve_transient_provider(self, container: Container) -> None:
        @container.provider(scope="transient")
        async def get_uuid() -> uuid.UUID:
            return uuid.uuid4()

        assert await container.aresolve(uuid.UUID) != await container.aresolve(
            uuid.UUID
        )

    async def test_async_resolve_synchronous_resource(
        self, container: Container
    ) -> None:
        @container.provider(scope="singleton")
        def msg() -> Iterator[str]:
            yield "test"

        assert await container.aresolve(str) == "test"

    def test_resolve_not_registered_instance(self, container: Container) -> None:
        with pytest.raises(
            LookupError,
            match=(
                "The provider interface `str` is either not registered, not provided, "
                "or not set in the scoped context. Please ensure that the provider "
                "interface is properly registered and that the class is decorated "
                "with a scope before attempting to use it."
            ),
        ):
            container.resolve(str)

    def test_resolve_non_strict_provider_scope_defined(
        self, container: Container
    ) -> None:
        @singleton
        class Service:
            pass

        _ = container.resolve(Service)

        provider = container.providers[Service]

        assert provider.call == Service
        assert provider.scope == "singleton"
        assert provider.interface == Service

    def test_resolve_non_strict_provider_scope_from_sub_provider_request(
        self,
        container: Container,
    ) -> None:
        @container.provider(scope="request")
        def ident() -> str:
            return "test"

        with container.request_context():
            _ = container.resolve(Service)

        assert Service in container.providers

        provider = container.providers[str]

        assert provider.call == ident
        assert provider.scope == "request"
        assert provider.interface is str

    def test_resolve_non_strict_provider_scope_from_sub_provider_transient(
        self,
        container: Container,
    ) -> None:
        @container.provider(scope="transient")
        def uuid_generator() -> Annotated[str, "uuid_generator"]:
            return str(uuid.uuid4())

        @dataclass
        class Entity:
            id: Annotated[str, "uuid_generator"]

        _ = container.resolve(Entity)

        assert container.providers[Entity].scope == "transient"

    def test_resolve_non_strict_nested_singleton_provider(
        self, container: Container
    ) -> None:
        @singleton
        class Repository:
            pass

        class Service:
            def __init__(self, repository: Repository) -> None:
                self.repository = repository

        with container.request_context():
            _ = container.resolve(Service)

        assert container.providers[Service].scope == "singleton"

    def test_resolve_non_strict_default_scope(self, container: Container) -> None:
        @dataclass
        class Repository:
            pass

        @dataclass
        class Service:
            repository: Repository

        _ = container.resolve(Service)

        assert container.providers[Service].scope == "transient"

    def test_resolve_non_strict_with_primitive_class(
        self, container: Container
    ) -> None:
        with pytest.raises(
            LookupError,
            match=(
                "The provider `tests.fixtures.Service` depends on `ident` of type "
                "`str`, which has not been registered or set. To resolve this, "
                "ensure that `ident` is registered before attempting to use it."
            ),
        ):
            _ = container.resolve(Service).ident

    @pytest.mark.skipif(sys.version_info < (3, 10), reason="Requires Python 3.10")
    def test_resolve_non_strict_with_custom_type(self, container: Container) -> None:
        class Klass:
            def __init__(
                self, value: "Union[str, Sequence[str], int, list[str]]"
            ) -> None:
                self.value = value

        with pytest.raises(
            LookupError,
            match=(
                "The provider `(.*?)` depends on `value` of type `(.*?)`, "
                "which has not been registered or set. To resolve this, "
                "ensure that `value` is registered before attempting to use it."
            ),
        ):
            _ = container.resolve(Klass)

    def test_resolve_non_strict_with_as_context_manager(
        self, container: Container
    ) -> None:
        @singleton
        class Resource:
            def __init__(self) -> None:
                self.entered = False
                self.exited = False

            def __enter__(self) -> Self:
                self.entered = True
                return self

            def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
                self.exited = True

        resource = container.resolve(Resource)

        assert resource.entered

        container.close()

        assert resource.exited

    async def test_resolve_non_strict_with_as_async_context_manager(
        self,
        container: Container,
    ) -> None:
        @singleton
        class Service:
            def __init__(self) -> None:
                self.entered = False
                self.exited = False

            async def __aenter__(self) -> Self:
                self.entered = True
                return self

            async def __aexit__(
                self, exc_type: Any, exc_value: Any, traceback: Any
            ) -> None:
                self.exited = True

        service = await container.aresolve(Service)

        assert service.entered

        await container.aclose()

        assert service.exited

    def test_resolve_non_strict_with_defaults(self, container: Container) -> None:
        @dataclass
        class Repo:
            name: str = "repo"

        class Service:
            def __init__(self, repo: Repo, name: str = "service") -> None:
                self.repo = repo
                self.name = name

        service = container.resolve(Service)

        assert service.name == "service"
        assert service.repo.name == "repo"

    async def test_resolve_non_strict_with_defaults_async_resolver(
        self,
        container: Container,
    ) -> None:
        @dataclass
        class Repo:
            name: str = "repo"

        class Service:
            def __init__(self, repo: Repo, name: str = "service") -> None:
                self.repo = repo
                self.name = name

        service = await container.aresolve(Service)

        assert service.name == "service"
        assert service.repo.name == "repo"

    def test_is_resolved(self, container: Container) -> None:
        @container.provider(scope="singleton")
        def message() -> str:
            return "test"

        _ = container.resolve(str)

        assert container.is_resolved(str)

    def test_is_resolved_transient(self, container: Container) -> None:
        @container.provider(scope="transient")
        def message() -> str:
            return "test"

        _ = container.resolve(str)

        assert not container.is_resolved(str)

    def test_is_resolved_false(self, container: Container) -> None:
        assert not container.is_resolved(str)

    def test_release_instance(self, container: Container) -> None:
        container.register(str, lambda: "test", scope="singleton")
        container.resolve(str)

        assert container.is_resolved(str)

        container.release(str)

        assert not container.is_resolved(str)

    def test_release_transient_instance(self, container: Container) -> None:
        container.register(str, lambda: "test", scope="transient")

        assert not container.is_resolved(str)

        container.release(str)

        assert not container.is_resolved(str)

    def test_resource_delegated_exception(self, container: Container) -> None:
        resource = Resource()

        @container.provider(scope="request")
        def resource_provider() -> Iterator[Resource]:
            try:
                yield resource
            except Exception:  # noqa
                resource.rollback()
                raise
            else:
                resource.commit()

        def _resolve() -> None:
            resource = container.resolve(Resource)
            resource.run()
            raise ValueError("error")

        with pytest.raises(ValueError, match="error"), container.request_context():
            _resolve()

        assert resource.called
        assert not resource.committed
        assert resource.rolled_back

    async def test_async_resource_delegated_exception(
        self, container: Container
    ) -> None:
        resource = Resource()

        @container.provider(scope="request")
        async def resource_provider() -> AsyncIterator[Resource]:
            try:
                yield resource
            except Exception:  # noqa
                resource.rollback()
                raise
            else:
                resource.commit()

        async def _resolve() -> None:
            resource = await container.aresolve(Resource)
            resource.run()
            raise ValueError("error")

        with pytest.raises(ValueError, match="error"):
            async with container.arequest_context():
                await _resolve()

        assert resource.called
        assert not resource.committed
        assert resource.rolled_back

    # Inspections

    def test_get_provider_arguments(self, container: Container) -> None:
        @container.provider(scope="singleton")
        def a() -> int:
            return 10

        @container.provider(scope="singleton")
        def b() -> float:
            return 1.0

        @container.provider(scope="singleton")
        def c() -> str:
            return "test"

        def service(a: int, b: float, *, c: str) -> Service:
            return Service(ident=f"{a}/{b}/{c}")

        provider = container.register(Service, service, scope="singleton")

        context = container._get_instance_context("singleton")

        kwargs = container._get_provided_kwargs(provider, context)

        assert kwargs == {"a": 10, "b": 1.0, "c": "test"}

    async def test_async_get_provider_arguments(self, container: Container) -> None:
        @container.provider(scope="singleton")
        async def a() -> int:
            return 10

        @container.provider(scope="singleton")
        async def b() -> float:
            return 1.0

        @container.provider(scope="singleton")
        async def c() -> str:
            return "test"

        async def service(a: int, b: float, *, c: str) -> Service:
            return Service(ident=f"{a}/{b}/{c}")

        provider = container.register(Service, service, scope="singleton")

        context = container._get_instance_context("singleton")

        kwargs = await container._aget_provided_kwargs(provider, context)

        assert kwargs == {"a": 10, "b": 1.0, "c": "test"}

    def test_create_transient_non_strict(self) -> None:
        @transient
        class Component:
            def __init__(self, name: str) -> None:
                self.name = name

        container = Container()

        instance = container.create(Component, name="test")

        assert instance.name == "test"

    def test_create_singleton_non_strict(self) -> None:
        @singleton
        class Component:
            def __init__(self, name: str) -> None:
                self.name = name

        container = Container()

        instance = container.create(Component, name="test")

        assert instance.name == "test"

    def test_create_scoped_non_strict(self) -> None:
        @request
        class Component:
            def __init__(self, name: str) -> None:
                self.name = name

        container = Container()

        with container.request_context():
            instance = container.create(Component, name="test")

        assert instance.name == "test"

    def test_create_non_existing_keyword_arg(self) -> None:
        @singleton
        class Component:
            pass

        container = Container()

        with pytest.raises(TypeError, match="takes no arguments"):
            container.create(Component, param="test")

    async def test_create_async_transient_non_strict(self) -> None:
        @transient
        class Component:
            def __init__(self, name: str) -> None:
                self.name = name

        container = Container()

        instance = await container.acreate(Component, name="test")

        assert instance.name == "test"

    async def test_create_async_singleton_non_strict(self) -> None:
        @singleton
        class Component:
            def __init__(self, name: str) -> None:
                self.name = name

        container = Container()

        instance = await container.acreate(Component, name="test")

        assert instance.name == "test"

    async def test_create_async_scoped_non_strict(self) -> None:
        @request
        class Component:
            def __init__(self, name: str) -> None:
                self.name = name

        container = Container()

        with container.request_context():
            instance = await container.acreate(Component, name="test")

        assert instance.name == "test"

    async def test_create_async_non_existing_keyword_arg(self) -> None:
        @singleton
        class Component:
            pass

        container = Container()

        with pytest.raises(TypeError, match="takes no arguments"):
            await container.acreate(Component, param="test")


class TestContainerInjector:
    def test_inject(self, container: Container) -> None:
        @container.provider(scope="singleton")
        def ident_provider() -> str:
            return "1000"

        @container.provider(scope="singleton")
        def service_provider(ident: str) -> Service:
            return Service(ident=ident)

        @container.inject
        def func(name: str, service: Service = auto) -> str:
            return f"{name} = {service.ident}"

        result = func(name="service ident")

        assert result == "service ident = 1000"

    @pytest.mark.skip(reason="disable until strict is enforced")
    def test_inject_missing_annotation(self, container: Container) -> None:
        def handler(name=auto) -> str:  # type: ignore
            return name  # type: ignore

        with pytest.raises(
            TypeError, match="Missing `(.*?).handler` parameter `name` annotation."
        ):
            container.inject(handler)

    @pytest.mark.skip(reason="disable until strict is enforced")
    def test_inject_unknown_dependency_using_strict_mode(self) -> None:
        container = Container()

        def handler(message: str = auto) -> None:
            pass

        with pytest.raises(
            LookupError,
            match=(
                "`(.*?).handler` has an unknown dependency parameter `message` "
                "with an annotation of `str`."
            ),
        ):
            container.inject(handler)

    def test_inject_auto_marker(self, container: Container) -> None:
        @container.provider(scope="singleton")
        def message() -> str:
            return "test"

        @container.inject
        def func(message: str = auto) -> str:
            return message

        result = func()

        assert result == "test"

    def test_inject_auto_marker_call(self, container: Container) -> None:
        @container.provider(scope="singleton")
        def message() -> str:
            return "test"

        @container.inject
        def func(message: str = auto()) -> str:
            return message

        result = func()

        assert result == "test"

    def test_inject_class(self, container: Container) -> None:
        @container.provider(scope="singleton")
        def ident_provider() -> str:
            return "1000"

        @container.provider(scope="singleton")
        def service_provider(ident: str) -> Service:
            return Service(ident=ident)

        @container.inject
        class Handler:
            def __init__(self, name: str, service: Service = auto) -> None:
                self.name = name
                self.service = service

            def handle(self) -> str:
                return f"{self.name} = {self.service.ident}"

        handler = Handler(name="service ident")

        result = handler.handle()

        assert result == "service ident = 1000"

    async def test_inject_with_sync_and_async_resources(
        self, container: Container
    ) -> None:
        def ident_provider() -> Iterator[str]:
            yield "1000"

        async def service_provider(ident: str) -> AsyncIterator[Service]:
            yield Service(ident=ident)

        container.register(str, ident_provider, scope="singleton")
        container.register(Service, service_provider, scope="singleton")

        await container.astart()

        @container.inject
        async def func(name: str, service: Service = auto) -> str:
            return f"{name} = {service.ident}"

        result = await func(name="service ident")

        assert result == "service ident = 1000"

    def test_run(self, container: Container) -> None:
        @container.provider(scope="singleton")
        def value1() -> Annotated[int, "value1"]:
            return 10

        @container.provider(scope="singleton")
        def value2() -> Annotated[int, "value2"]:
            return 20

        def sum_handler(
            value1: int,
            value2: Annotated[int, "value1"] = auto,
            value3: Annotated[int, "value2"] = auto,
        ) -> int:
            return value1 + value2 + value3

        result = container.run(sum_handler, value1=30)

        assert result == 60

    def test_run_cached(self, container: Container) -> None:
        @container.provider(scope="singleton")
        def message() -> str:
            return "hello"

        def handler(message: str = auto) -> str:
            return message

        _ = container.run(handler)
        _ = container.run(handler)

        assert handler in container._inject_cache
