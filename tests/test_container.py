import asyncio
import logging
import sys
import threading
import time
import uuid
from collections.abc import AsyncIterator, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any, Callable, Union
from unittest import mock

import pytest
from typing_extensions import Self

from anydi import (
    Container,
    Module,
    Scope,
    auto,
    injectable,
    provider,
    request,
    singleton,
    transient,
)
from anydi._types import (
    Event,
    InjectableDecoratorArgs,
    ProviderArgs,
    ProviderDecoratorArgs,
    ProviderKind,
)

from tests.fixtures import (
    Class,
    Resource,
    Service,
    TestModule,
    async_event,
    async_generator,
    coro,
    event,
    func,
    generator,
    iterator,
)
from tests.scan_app import ScanAppModule


@pytest.fixture
def container() -> Container:
    return Container()


class TestContainer:
    def test_default_properties(self) -> None:
        container = Container()

        assert not container.strict
        assert container.default_scope == "transient"
        assert not container.testing

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
    def test_create_provider(
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
    def test_create_provider_interface(
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
    def test_create_provider_event(
        self,
        container: Container,
        call: Callable[..., Any],
        kind: ProviderKind,
    ) -> None:
        provider = container._register_provider(call, "singleton")

        assert provider.kind == kind
        assert issubclass(provider.interface, Event)

    def test_create_provider_with_interface(self, container: Container) -> None:
        provider = container._register_provider(lambda: "hello", "singleton", str)

        assert provider.interface is str

    def test_create_provider_with_none(self, container: Container) -> None:
        with pytest.raises(
            TypeError, match="Missing `(.*?)` provider return annotation."
        ):
            container._register_provider(lambda: "hello", "singleton", None)

    def test_create_provider_provider_without_return_annotation(
        self, container: Container
    ) -> None:
        def provide_message():  # type: ignore[no-untyped-def]
            return "hello"

        with pytest.raises(
            TypeError, match="Missing `(.*?)` provider return annotation."
        ):
            container._register_provider(provide_message, "singleton")

    def test_create_provider_not_callable(self, container: Container) -> None:
        with pytest.raises(
            TypeError,
            match=(
                "The provider `Test` is invalid because it is not a callable object. "
                "Only callable providers are allowed."
            ),
        ):
            container._register_provider("Test", "singleton")  # type: ignore[arg-type]

    def test_create_provider_iterator_no_arg_not_allowed(
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

    def test_create_provider_unsupported_scope(self, container: Container) -> None:
        with pytest.raises(
            ValueError,
            match=(
                "The provider `(.*?)` scope is invalid. Only the following scopes "
                "are supported: transient, singleton, request. "
                "Please use one of the supported scopes when registering a provider."
            ),
        ):
            container._register_provider(generator, "other")  # type: ignore[arg-type]

    def test_create_provider_transient_resource_not_allowed(
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

    def test_create_provider_without_annotation(self, container: Container) -> None:
        def service_ident() -> str:
            return "10000"

        def service(ident) -> Service:  # type: ignore[no-untyped-def]
            return Service(ident=ident)

        with pytest.raises(
            TypeError, match="Missing provider `(.*?)` dependency `ident` annotation."
        ):
            container._register_provider(service, "singleton")

    def test_create_provider_positional_only_parameter_not_allowed(
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
                ProviderArgs(call=lambda: "test", scope="singleton", interface=str),
                ProviderArgs(call=lambda: 1, scope="singleton", interface=int),
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
            match=(
                "The provider `Test` is invalid because it is not a callable object. "
                "Only callable providers are allowed."
            ),
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
        def provide_service() -> Service:
            time.sleep(0.1)
            return Service(ident="test")

        service_ids = set()

        def use_service() -> None:
            service = container.resolve(Service)
            service_ids.add(id(service))

        threads = [threading.Thread(target=use_service) for _ in range(5)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(service_ids) == 1

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
        async def provide_service() -> Service:
            await asyncio.sleep(0.1)
            return Service(ident="test")

        service_ids = set()

        async def use_service() -> None:
            service = await container.aresolve(Service)
            service_ids.add(id(service))

        tasks = [use_service() for _ in range(5)]

        await asyncio.gather(*tasks)

        assert len(service_ids) == 1

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
                "The provider interface for `str` has not been registered. Please "
                "ensure that the provider interface is properly registered before "
                "attempting to use it."
            ),
        ):
            container.resolve(str)

    def test_resolve_non_strict_provider_scope_defined(
        self, container: Container
    ) -> None:
        class Service:
            __scope__ = "singleton"

        _ = container.resolve(Service)

        provider = container.providers[Service]

        assert provider.call == Service
        assert provider.scope == "singleton"
        assert provider.interface == Service

    def test_resolve_non_strict_annotated(self, container: Container) -> None:
        class Service:
            pass

        service_1 = container.resolve(Annotated[Service, "service_1"])
        service_2 = container.resolve(Annotated[Service, "service_2"])

        assert service_1 != service_2
        assert container.is_registered(Annotated[Service, "service_1"])
        assert container.is_registered(Annotated[Service, "service_2"])

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
        @dataclass
        class Repository:
            __scope__ = "singleton"

        @dataclass
        class Service:
            repository: Repository

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
        class Resource:
            __scope__ = "singleton"

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
        class Service:
            __scope__ = "singleton"

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

    def test_override_instance(self) -> None:
        origin_name = "origin"
        overridden_name = "overridden"

        container = Container(testing=True)

        @container.provider(scope="singleton")
        def name() -> str:
            return origin_name

        with container.override(str, overridden_name):
            assert container.resolve(str) == overridden_name

        assert container.resolve(str) == origin_name

    def test_override_instance_provider_not_registered_using_strict_mode(self) -> None:
        container = Container(strict=True, testing=True)

        with pytest.raises(
            LookupError, match="The provider interface `str` not registered."
        ):
            with container.override(str, "test"):
                ...

    def test_override_instance_transient_provider(self) -> None:
        overridden_uuid = uuid.uuid4()

        container = Container(testing=True)

        @container.provider(scope="transient")
        def uuid_provider() -> uuid.UUID:
            return uuid.uuid4()

        with container.override(uuid.UUID, overridden_uuid):
            assert container.resolve(uuid.UUID) == overridden_uuid

        assert container.resolve(uuid.UUID) != overridden_uuid

    def test_override_instance_resource_provider(self) -> None:
        origin = "origin"
        overridden = "overridden"

        container = Container(testing=True)

        @container.provider(scope="singleton")
        def message() -> Iterator[str]:
            yield origin

        with container.override(str, overridden):
            assert container.resolve(str) == overridden

        assert container.resolve(str) == origin

    async def test_override_instance_async_resource_provider(self) -> None:
        origin = "origin"
        overridden = "overridden"

        container = Container(testing=True)

        @container.provider(scope="singleton")
        async def message() -> AsyncIterator[str]:
            yield origin

        with container.override(str, overridden):
            assert (await container.aresolve(str)) == overridden

    def test_override_instance_testing(self) -> None:
        container = Container(strict=False, testing=True)
        container.register(Annotated[str, "param"], lambda: "param", scope="singleton")

        class UserRepo:
            def get_user(self) -> str:
                return "user"

        @dataclass
        class UserService:
            __scope__ = "singleton"

            repo: UserRepo
            param: Annotated[str, "param"]

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

    async def test_override_instance_testing_async_resolved(self) -> None:
        container = Container(strict=False, testing=True)
        container.register(Annotated[str, "param"], lambda: "param", scope="singleton")

        @dataclass
        class UserService:
            __scope__ = "singleton"

            param: Annotated[str, "param"]

            def process(self) -> dict[str, str]:
                return {
                    "param": self.param,
                }

        user_service = await container.aresolve(UserService)

        with container.override(Annotated[str, "param"], "mock"):
            assert user_service.process() == {
                "param": "mock",
            }

    def test_override_instance_testing_in_strict_mode(self) -> None:
        container = Container(strict=True, testing=True)

        @dataclass
        class Settings:
            name: str

        @container.provider(scope="singleton")
        def provide_settings() -> Settings:
            return Settings(name="test")

        @container.provider(scope="singleton")
        def provide_service(settings: Settings) -> Service:
            return Service(ident=settings.name)

        service = container.resolve(Service)

        assert service.ident == "test"

    def test_override_instance_first_testing(self) -> None:
        container = Container(strict=True, testing=True)

        @dataclass
        class Item:
            name: str

        @dataclass
        class ItemRepository:
            items: list[Item]

            def all(self) -> list[Item]:
                return self.items

        @dataclass
        class ItemService:
            repo: ItemRepository

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
        @dataclass
        class ServiceWithProp:
            name: str = "origin"
            items: list[str] = field(default_factory=list)

        container = Container(testing=True)

        service = container.resolve(ServiceWithProp)

        assert service.name == "origin"
        assert service.items == []

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

        context = container._get_scoped_context("singleton")

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

        context = container._get_scoped_context("singleton")

        kwargs = await container._aget_provided_kwargs(provider, context)

        assert kwargs == {"a": 10, "b": 1.0, "c": "test"}

    def test_create_transient_non_strict(self) -> None:
        @dataclass
        class Component:
            __scope__ = "transient"

            name: str

        container = Container(strict=False)

        instance = container.create(Component, name="test")

        assert instance.name == "test"

    def test_create_singleton_non_strict(self) -> None:
        @dataclass
        class Component:
            __scope__ = "singleton"

            name: str

        container = Container(strict=False)

        instance = container.create(Component, name="test")

        assert instance.name == "test"

    def test_create_scoped_non_strict(self) -> None:
        @dataclass
        class Component:
            __scope__ = "request"

            name: str

        container = Container(strict=False)

        with container.request_context():
            instance = container.create(Component, name="test")

        assert instance.name == "test"

    def test_create_non_existing_keyword_arg(self) -> None:
        class Component:
            __scope__ = "singleton"

        container = Container(strict=False)

        with pytest.raises(TypeError, match="takes no arguments"):
            container.create(Component, param="test")

    async def test_create_async_transient_non_strict(self) -> None:
        @dataclass
        class Component:
            __scope__ = "transient"

            name: str

        container = Container(strict=False)

        instance = await container.acreate(Component, name="test")

        assert instance.name == "test"

    async def test_create_async_singleton_non_strict(self) -> None:
        @dataclass
        class Component:
            __scope__ = "singleton"

            name: str

        container = Container(strict=False)

        instance = await container.acreate(Component, name="test")

        assert instance.name == "test"

    async def test_create_async_scoped_non_strict(self) -> None:
        @dataclass
        class Component:
            __scope__ = "request"

            name: str

        container = Container(strict=False)

        with container.request_context():
            instance = await container.acreate(Component, name="test")

        assert instance.name == "test"

    async def test_create_async_non_existing_keyword_arg(self) -> None:
        class Component:
            __scope__ = "singleton"

        container = Container(strict=False)

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

    def test_inject_auto_registered_log_message(
        self, container: Container, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.DEBUG, logger="anydi"):

            @container.inject
            def handler(service: Service = auto) -> None:
                pass

            assert caplog.messages == [
                "Cannot validate the `tests.test_container.TestContainerInjector"
                ".test_inject_auto_registered_log_message.<locals>.handler` parameter "
                "`service` with an annotation of `tests.fixtures.Service due to "
                "being in non-strict mode. It will be validated at the first call."
            ]

    def test_inject_missing_annotation(self, container: Container) -> None:
        def handler(name=auto) -> str:  # type: ignore[no-untyped-def]
            return name  # type: ignore[no-any-return]

        with pytest.raises(
            TypeError, match="Missing `(.*?).handler` parameter `name` annotation."
        ):
            container.inject(handler)

    def test_inject_unknown_dependency_using_strict_mode(self) -> None:
        container = Container(strict=True)

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

    def test_inject_dataclass(self, container: Container) -> None:
        @container.provider(scope="singleton")
        def ident_provider() -> str:
            return "1000"

        @container.provider(scope="singleton")
        def service_provider(ident: str) -> Service:
            return Service(ident=ident)

        @container.inject
        @dataclass
        class Handler:
            name: str
            service: Service = auto

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


class TestContainerModule:
    def test_register_modules(self) -> None:
        container = Container(modules=[TestModule])

        assert container.is_registered(Annotated[str, "msg1"])
        assert container.is_registered(Annotated[str, "msg2"])

    def test_register_module_class(self, container: Container) -> None:
        container.register_module(TestModule)

        assert container.is_registered(Annotated[str, "msg1"])
        assert container.is_registered(Annotated[str, "msg2"])

    def test_register_module_instance(self, container: Container) -> None:
        container.register_module(TestModule())

        assert container.is_registered(Annotated[str, "msg1"])
        assert container.is_registered(Annotated[str, "msg2"])

    def test_register_module_path(self, container: Container) -> None:
        container.register_module("tests.test_container.TestModule")

        assert container.is_registered(Annotated[str, "msg1"])
        assert container.is_registered(Annotated[str, "msg2"])

    def test_register_module_function(self, container: Container) -> None:
        def configure(_container: Container) -> None:
            _container.register(str, lambda: "Message 1", scope="singleton")

        container.register_module(configure)

        assert container.is_registered(str)

    def test_register_module_ordered_providers(self, container: Container) -> None:
        class OrderedModule(Module):
            @provider(scope="singleton")
            def dep3(self) -> Annotated[str, "dep3"]:
                return "dep3"

            @provider(scope="singleton")
            def dep1(self) -> Annotated[str, "dep1"]:
                return "dep1"

            @provider(scope="singleton")
            def dep2(self) -> Annotated[str, "dep2"]:
                return "dep2"

        container.register_module(OrderedModule)

        assert list(container.providers.keys()) == [
            Annotated[str, "dep3"],
            Annotated[str, "dep1"],
            Annotated[str, "dep2"],
        ]


class TestContainerScanning:
    def test_scan(self, container: Container) -> None:
        container.register_module(ScanAppModule)
        container.scan(["tests.scan_app"])

        from .scan_app.a.a3.handlers import a_a3_handler_1, a_a3_handler_2

        assert a_a3_handler_1() == "a.a1.str_provider"
        assert a_a3_handler_2().ident == "a.a1.str_provider"

    def test_scan_single_package(self, container: Container) -> None:
        container.register_module(ScanAppModule)
        container.scan("tests.scan_app.a.a3.handlers")

        from .scan_app.a.a3.handlers import a_a3_handler_1

        assert a_a3_handler_1() == "a.a1.str_provider"

    def test_scan_non_existing_tag(self, container: Container) -> None:
        container.scan(["tests.scan_app"], tags=["non_existing_tag"])

        assert not container.providers

    def test_scan_tagged(self, container: Container) -> None:
        container.register_module(ScanAppModule)
        container.scan(["tests.scan_app.a"], tags=["inject"])

        from .scan_app.a.a3.handlers import a_a3_handler_1

        assert a_a3_handler_1() == "a.a1.str_provider"


class TestDecorators:
    def test_provider_decorator(self) -> None:
        class TestModule(Module):
            @provider(scope="singleton", override=True)
            def provider(self) -> str:
                return "test"

        assert getattr(TestModule.provider, "__provider__") == ProviderDecoratorArgs(
            scope="singleton",
            override=True,
        )

    def test_request_decorator(self) -> None:
        request(Service)

        assert getattr(Service, "__scope__") == "request"

    def test_transient_decorator(self) -> None:
        transient(Service)

        assert getattr(Service, "__scope__") == "transient"

    def test_singleton_decorator(self) -> None:
        singleton(Service)

        assert getattr(Service, "__scope__") == "singleton"

    def test_injectable_decorator_no_args(self) -> None:
        @injectable
        def my_func() -> None:
            pass

        assert getattr(my_func, "__injectable__") == InjectableDecoratorArgs(
            wrapped=True,
            tags=None,
        )

    def test_injectable_decorator_no_args_provided(self) -> None:
        @injectable()
        def my_func() -> None:
            pass

        assert getattr(my_func, "__injectable__") == InjectableDecoratorArgs(
            wrapped=True,
            tags=None,
        )

    def test_injectable_decorator(self) -> None:
        @injectable(tags=["tag1", "tag2"])
        def my_func() -> None:
            pass

        assert getattr(my_func, "__injectable__") == InjectableDecoratorArgs(
            wrapped=True,
            tags=["tag1", "tag2"],
        )
