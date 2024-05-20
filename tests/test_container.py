import logging
import uuid
from dataclasses import dataclass
from typing import (
    Any,
    AsyncIterator,
    Dict,
    Iterator,
    List,
    Sequence,
    Tuple,
    Type,
    Union,
)

import pytest
from typing_extensions import Annotated

from anydi import Container, Provider, Scope, auto, dep, request, singleton, transient

from tests.fixtures import Service


@pytest.fixture
def container() -> Container:
    return Container()


def test_default_strict_disabled(container: Container) -> None:
    assert not container.strict


def test_register_provider(container: Container) -> None:
    def provider_obj() -> str:
        return "test"

    provider = container.register(str, provider_obj, scope="transient")

    assert provider.obj == provider_obj
    assert provider.scope == "transient"


def test_register_provider_already_registered(container: Container) -> None:
    container.register(str, lambda: "test", scope="singleton")

    with pytest.raises(LookupError) as exc_info:
        container.register(str, lambda: "other", scope="singleton")

    assert str(exc_info.value) == "The provider interface `str` already registered."


def test_register_provider_override(container: Container) -> None:
    container.register(str, lambda: "old", scope="singleton")

    def new_provider_obj() -> str:
        return "new"

    provider = container.register(
        str, new_provider_obj, scope="singleton", override=True
    )

    assert provider.obj == new_provider_obj


def test_register_provider_named(container: Container) -> None:
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


def test_register_providers_via_constructor() -> None:
    container = Container(
        providers={
            str: Provider(obj=lambda: "test", scope="singleton"),
            int: Provider(obj=lambda: 1, scope="singleton"),
        }
    )

    assert container.is_registered(str)
    assert container.is_registered(int)


def test_register_provider_with_invalid_scope(container: Container) -> None:
    with pytest.raises(ValueError) as exc_info:
        container.register(
            str,
            lambda: "test",
            scope="invalid",  # type: ignore[arg-type]
        )

    assert str(exc_info.value) == (
        "The scope provided is invalid. Only the following scopes are supported: "
        "transient, singleton, request. Please use one of the supported scopes when "
        "registering a provider."
    )


def test_register_provider_invalid_transient_resource(container: Container) -> None:
    def provider_obj() -> Iterator[str]:
        yield "test"

    with pytest.raises(TypeError) as exc_info:
        container.register(str, provider_obj, scope="transient")

    assert str(exc_info.value) == (
        "The resource provider `tests.test_container"
        ".test_register_provider_invalid_transient_resource.<locals>.provider_obj` is "
        "attempting to register with a transient scope, which is not allowed. Please "
        "update the provider's scope to an appropriate value before registering it."
    )


def test_register_provider_invalid_transient_async_resource(
    container: Container,
) -> None:
    async def provider_obj() -> AsyncIterator[str]:
        yield "test"

    with pytest.raises(TypeError) as exc_info:
        container.register(str, provider_obj, scope="transient")

    assert str(exc_info.value) == (
        "The resource provider `tests.test_container"
        ".test_register_provider_invalid_transient_async_resource"
        ".<locals>.provider_obj` is attempting to register with a transient scope, "
        "which is not allowed. Please update the provider's scope to an "
        "appropriate value before registering it."
    )


def test_register_provider_valid_resource(container: Container) -> None:
    def provider_obj1() -> Iterator[str]:
        yield "test"

    def provider_obj2() -> Iterator[int]:
        yield 100

    container.register(str, provider_obj1, scope="singleton")
    container.register(int, provider_obj2, scope="request")


def test_register_provider_valid_async_resource(container: Container) -> None:
    async def provider_obj1() -> AsyncIterator[str]:
        yield "test"

    async def provider_obj2() -> AsyncIterator[int]:
        yield 100

    container.register(str, provider_obj1, scope="singleton")
    container.register(int, provider_obj2, scope="request")


def test_register_invalid_provider_type(container: Container) -> None:
    with pytest.raises(TypeError) as exc_info:
        container.register(str, "Test", scope="singleton")  # type: ignore[arg-type]

    assert str(exc_info.value) == (
        "The provider `Test` is invalid because it is not a callable object. Only "
        "callable providers are allowed. Please update the provider to a callable "
        "object before attempting to register it."
    )


def test_register_valid_class_provider(container: Container) -> None:
    class Klass:
        pass

    provider = container.register(str, Klass, scope="singleton")

    assert provider.is_class


@pytest.mark.parametrize(
    "scope1, scope2, scope3, valid",
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
    container: Container, scope1: Scope, scope2: Scope, scope3: Scope, valid: bool
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


def test_register_provider_match_scopes_error(container: Container) -> None:
    def provider_int() -> int:
        return 1000

    def provider_str(n: int) -> str:
        return f"{n}"

    container.register(int, provider_int, scope="request")

    with pytest.raises(ValueError) as exc_info:
        container.register(str, provider_str, scope="singleton")

    assert str(exc_info.value) == (
        "The provider `tests.test_container.test_register_provider_match_scopes_error"
        ".<locals>.provider_str` with a singleton scope was attempted to be registered "
        "with the provider `tests.test_container"
        ".test_register_provider_match_scopes_error.<locals>.provider_int` with a "
        "`request` scope, which is not allowed. Please ensure that all providers are "
        "registered with matching scopes."
    )


def test_register_provider_without_annotation(container: Container) -> None:
    def service_ident() -> str:
        return "10000"

    def service(ident) -> Service:  # type: ignore[no-untyped-def]
        return Service(ident=ident)

    container.register(str, service_ident, scope="singleton")

    with pytest.raises(TypeError) as exc_info:
        container.register(Service, service, scope="singleton")

    assert str(exc_info.value) == (
        "Missing provider "
        "`tests.test_container.test_register_provider_without_annotation"
        ".<locals>.service` dependency `ident` annotation."
    )


def test_register_provider_with_not_registered_sub_provider(
    container: Container,
) -> None:
    def dep2(dep1: int) -> str:
        return str(dep1)

    with pytest.raises(ValueError) as exc_info:
        container.register(str, dep2, scope="singleton")

    assert str(exc_info.value) == (
        "The provider "
        "`tests.test_container.test_register_provider_with_not_registered_sub_provider"
        ".<locals>.dep2` depends on `dep1` of type `int`, which has not been "
        "registered. To resolve this, ensure that `dep1` is registered "
        "before attempting to use it."
    )


def test_register_events(container: Container) -> None:
    events = []

    @container.provider(scope="singleton")
    def message() -> str:
        return "test"

    @container.provider(scope="singleton")
    def event_1(message: str) -> Iterator[None]:
        events.append(f"event_1: before {message}")
        yield
        events.append(f"event_1: after {message}")

    @container.provider(scope="singleton")
    def event_2(message: str) -> Iterator[None]:
        events.append(f"event_2: before {message}")
        yield
        events.append(f"event_2: after {message}")

    container.start()

    assert events == [
        "event_1: before test",
        "event_2: before test",
    ]

    container.close()

    assert events == [
        "event_1: before test",
        "event_2: before test",
        "event_2: after test",
        "event_1: after test",
    ]


async def test_register_async_events(container: Container) -> None:
    events = []

    @container.provider(scope="singleton")
    def message() -> str:
        return "test"

    @container.provider(scope="singleton")
    async def event_1(message: str) -> AsyncIterator[None]:
        events.append(f"event_1: before {message}")
        yield
        events.append(f"event_1: after {message}")

    @container.provider(scope="singleton")
    def event_2(message: str) -> Iterator[None]:
        events.append(f"event_2: before {message}")
        yield
        events.append(f"event_2: after {message}")

    await container.astart()

    assert events == [
        "event_1: before test",
        "event_2: before test",
    ]

    await container.aclose()

    assert events == [
        "event_1: before test",
        "event_2: before test",
        "event_2: after test",
        "event_1: after test",
    ]


def test_unregister_provider(container: Container) -> None:
    container.register(str, lambda: "test", scope="singleton")

    assert container.is_registered(str)

    container.unregister(str)

    assert not container.is_registered(str)


def test_unregister_request_scoped_provider(container: Container) -> None:
    container.register(str, lambda: "test", scope="request")

    assert container.is_registered(str)

    container.unregister(str)

    assert not container.is_registered(str)


def test_unregister_not_registered_provider(container: Container) -> None:
    with pytest.raises(LookupError) as exc_info:
        container.unregister(str)

    assert str(exc_info.value) == "The provider interface `str` not registered."


def test_inject_auto_registered_log_message(
    container: Container, caplog: pytest.LogCaptureFixture
) -> None:
    class Service:
        pass

    with caplog.at_level(logging.DEBUG, logger="anydi"):

        @container.inject
        def handler(service: Service = dep()) -> None:
            pass

        assert caplog.messages == [
            "Cannot validate the `tests.test_container"
            ".test_inject_auto_registered_log_message.<locals>.handler` parameter "
            "`service` with an annotation of `tests.test_container"
            ".test_inject_auto_registered_log_message.<locals>.Service due to being "
            "in non-strict mode. It will be validated at the first call."
        ]


# Lifespan


def test_start_and_close_singleton_context(container: Container) -> None:
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


def test_request_context(container: Container) -> None:
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


async def test_astart_and_aclose_singleton_context(container: Container) -> None:
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


async def test_arequest_context(container: Container) -> None:
    events = []

    async def dep1() -> AsyncIterator[str]:
        events.append("dep1:before")
        yield "test"
        events.append("dep1:after")

    container.register(str, dep1, scope="request")

    async with container.arequest_context():
        assert await container.aresolve(str) == "test"

    assert events == ["dep1:before", "dep1:after"]


def test_reset_resolved_instances(container: Container) -> None:
    container.register(str, lambda: "test", scope="singleton")
    container.register(int, lambda: 1, scope="singleton")

    container.resolve(str)
    container.resolve(int)

    assert container.is_resolved(str)
    assert container.is_resolved(int)

    container.reset()

    assert not container.is_resolved(str)
    assert not container.is_resolved(int)


# Instance


def test_resolve_singleton_scoped(container: Container) -> None:
    instance = "test"

    container.register(str, lambda: instance, scope="singleton")

    assert container.resolve(str) == instance


def test_resolve_singleton_scoped_not_started(container: Container) -> None:
    @container.provider(scope="singleton")
    def message() -> Iterator[str]:
        yield "test"

    assert container.resolve(str) == "test"


def test_resolve_singleton_scoped_resource(container: Container) -> None:
    instance = "test"

    def provide() -> Iterator[str]:
        yield instance

    container.register(str, provide, scope="singleton")
    container.start()

    assert container.resolve(str) == instance


def test_resolve_singleton_scoped_started_with_async_resource_provider(
    container: Container,
) -> None:
    instance = "test"

    async def provide() -> AsyncIterator[str]:
        yield instance

    container.register(str, provide, scope="singleton")

    with pytest.raises(TypeError) as exc_info:
        container.start()

    assert str(exc_info.value) == (
        "The provider `tests.test_container.test_resolve_singleton_scoped_started_with_"
        "async_resource_provider.<locals>.provide` cannot be started in synchronous "
        "mode because it is an asynchronous provider. Please start the provider "
        "in asynchronous mode before using it."
    )


def test_resolve_singleton_resource(container: Container) -> None:
    instance = "test"

    def provide() -> Iterator[str]:
        yield instance

    container.register(str, provide, scope="singleton")

    container.resolve(str)


async def test_resolve_singleton_async_resource(container: Container) -> None:
    instance = "test"

    def provide() -> Iterator[str]:
        yield instance

    container.register(str, provide, scope="singleton")

    await container.astart()

    assert container.resolve(str) == instance


async def test_resolve_singleton_async_and_sync_resources(container: Container) -> None:
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
    container: Container,
) -> None:
    instance = "test"

    async def provide() -> AsyncIterator[str]:
        yield instance

    container.register(str, provide, scope="singleton")

    with pytest.raises(TypeError) as exc_info:
        container.resolve(str)

    assert str(exc_info.value) == (
        "The provider `tests.test_container"
        ".test_resolved_singleton_async_resource_not_started.<locals>.provide` "
        "cannot be started in synchronous mode because it is an asynchronous provider. "
        "Please start the provider in asynchronous mode before using it."
    )


def test_resolve_request_scoped(container: Container) -> None:
    instance = "test"

    container.register(str, lambda: instance, scope="request")

    with container.request_context():
        assert container.resolve(str) == instance


def test_resolve_request_scoped_not_started(container: Container) -> None:
    instance = "test"

    container.register(str, lambda: instance, scope="request")

    with pytest.raises(LookupError) as exc_info:
        assert container.resolve(str)

    assert str(exc_info.value) == (
        "The request context has not been started. Please ensure that the request "
        "context is properly initialized before attempting to use it."
    )


def test_resolve_transient_scoped(container: Container) -> None:
    container.register(uuid.UUID, uuid.uuid4, scope="transient")

    assert container.resolve(uuid.UUID) != container.resolve(uuid.UUID)


def test_sync_resolve_transient_async_provider(container: Container) -> None:
    @container.provider(scope="transient")
    async def get_uuid() -> uuid.UUID:
        return uuid.uuid4()

    with pytest.raises(TypeError) as exc_info:
        container.resolve(uuid.UUID)

    assert str(exc_info.value) == (
        "The instance for the coroutine provider "
        "`tests.test_container.test_sync_resolve_transient_async_provider"
        ".<locals>.get_uuid` cannot be created in synchronous mode."
    )


async def test_async_resolve_transient_provider(container: Container) -> None:
    @container.provider(scope="transient")
    async def get_uuid() -> uuid.UUID:
        return uuid.uuid4()

    assert await container.aresolve(uuid.UUID) != await container.aresolve(uuid.UUID)


async def test_async_resolve_synchronous_resource(container: Container) -> None:
    @container.provider(scope="singleton")
    def msg() -> Iterator[str]:
        yield "test"

    assert await container.aresolve(str) == "test"


def test_resolve_not_registered_instance(container: Container) -> None:
    with pytest.raises(Exception) as exc_info:
        container.resolve(str)

    assert str(exc_info.value) == (
        "The provider interface for `str` has not been registered. Please ensure that "
        "the provider interface is properly registered before attempting to use it."
    )


def test_resolve_non_strict_provider_scope_defined(container: Container) -> None:
    class Service:
        __scope__ = "singleton"

    _ = container.resolve(Service)

    assert container.providers == {Service: Provider(obj=Service, scope="singleton")}


def test_resolve_non_strict_provider_scope_from_sub_provider_request(
    container: Container,
) -> None:
    @container.provider(scope="request")
    def message() -> str:
        return "test"

    @dataclass
    class Service:
        message: str

    with container.request_context():
        _ = container.resolve(Service)

    assert container.providers == {
        str: Provider(obj=message, scope="request"),
        Service: Provider(obj=Service, scope="request"),
    }


def test_resolve_non_strict_provider_scope_from_sub_provider_transient(
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


def test_resolve_non_strict_nested_singleton_provider(container: Container) -> None:
    @dataclass
    class Repository:
        __scope__ = "singleton"

    @dataclass
    class Service:
        repository: Repository

    with container.request_context():
        _ = container.resolve(Service)

    assert container.providers[Service].scope == "singleton"


def test_resolve_non_strict_default_scope(container: Container) -> None:
    @dataclass
    class Repository:
        pass

    @dataclass
    class Service:
        repository: Repository

    _ = container.resolve(Service)

    assert container.providers[Service].scope == "transient"


def test_resolve_non_strict_with_primitive_class(container: Container) -> None:
    @dataclass
    class Service:
        name: str

    with pytest.raises(LookupError) as exc_info:
        _ = container.resolve(Service).name

    assert str(exc_info.value) == (
        "The provider interface for `str` has not been registered. "
        "Please ensure that the provider interface is properly registered "
        "before attempting to use it."
    )


def test_resolve_non_strict_with_custom_type(container: Container) -> None:
    class Klass:
        def __init__(
            self, value: "Union[str, Sequence[str], int, List[str]]"
        ) -> None:
            self.value = value

    with pytest.raises(LookupError) as exc_info:
        _ = container.resolve(Klass)

    assert str(exc_info.value) == (
        "The provider interface for "
        "`typing.Union[str, collections.abc.Sequence[str], int, list[str]]` has not "
        "been registered. Please ensure that the provider interface is properly "
        "registered before attempting to use it."
    )


def test_is_resolved(container: Container) -> None:
    assert not container.is_resolved(str)


def test_release_instance(container: Container) -> None:
    container.register(str, lambda: "test", scope="singleton")
    container.resolve(str)

    assert container.is_resolved(str)

    container.release(str)

    assert not container.is_resolved(str)


def test_override_instance(container: Container) -> None:
    origin_name = "origin"
    overriden_name = "overriden"

    @container.provider(scope="singleton")
    def name() -> str:
        return origin_name

    with container.override(str, overriden_name):
        assert container.resolve(str) == overriden_name

    assert container.resolve(str) == origin_name


def test_override_instance_provider_not_registered_using_strict_mode() -> None:
    container = Container(strict=True)

    with pytest.raises(LookupError) as exc_info:
        with container.override(str, "test"):
            pass

    assert str(exc_info.value) == "The provider interface `str` not registered."


def test_override_instance_transient_provider(container: Container) -> None:
    overriden_uuid = uuid.uuid4()

    @container.provider(scope="transient")
    def uuid_provider() -> uuid.UUID:
        return uuid.uuid4()

    with container.override(uuid.UUID, overriden_uuid):
        assert container.resolve(uuid.UUID) == overriden_uuid

    assert container.resolve(uuid.UUID) != overriden_uuid


def test_override_instance_resource_provider(container: Container) -> None:
    origin = "origin"
    overriden = "overriden"

    @container.provider(scope="singleton")
    def message() -> Iterator[str]:
        yield origin

    with container.override(str, overriden):
        assert container.resolve(str) == overriden

    assert container.resolve(str) == origin


async def test_override_instance_async_resource_provider(container: Container) -> None:
    origin = "origin"
    overriden = "overriden"

    @container.provider(scope="singleton")
    async def message() -> AsyncIterator[str]:
        yield origin

    with container.override(str, overriden):
        assert container.resolve(str) == overriden


# Inspections


@pytest.mark.parametrize(
    "annotation, expected",
    [
        (str, str),
        (int, int),
        (Service, Service),
        (Iterator[Service], Service),
        (AsyncIterator[Service], Service),
        (Dict[str, Any], Dict[str, Any]),
        (List[str], List[str]),
        ("List[str]", List[str]),
        (Tuple[str, ...], Tuple[str, ...]),
        ("Tuple[str, ...]", Tuple[str, ...]),
        ('Annotated[str, "name"]', Annotated[str, "name"]),
    ],
)
def test_get_supported_provider_annotation(
    container: Container, annotation: Type[Any], expected: Type[Any]
) -> None:
    def provider() -> annotation:  # type: ignore[valid-type]
        return object()

    assert container._get_provider_annotation(provider) == expected


def test_get_provider_annotation_missing(container: Container) -> None:
    def provider():  # type: ignore[no-untyped-def]
        return object()

    with pytest.raises(TypeError) as exc_info:
        container._get_provider_annotation(provider)

    assert str(exc_info.value) == (
        "Missing `tests.test_container.test_get_provider_annotation_missing.<locals>"
        ".provider` provider return annotation."
    )


def test_get_provider_annotation_resource_without_args(container: Container) -> None:
    def provider() -> Iterator:  # type: ignore[type-arg]
        yield

    with pytest.raises(TypeError) as exc_info:
        container._get_provider_annotation(provider)

    assert str(exc_info.value) == (
        "Cannot use `tests.test_container"
        ".test_get_provider_annotation_resource_without_args.<locals>.provider` "
        "resource type annotation without actual type."
    )


def test_get_provider_arguments(container: Container) -> None:
    @container.provider(scope="singleton")
    def a() -> int:
        return 10

    @container.provider(scope="singleton")
    def b() -> float:
        return 1.0

    @container.provider(scope="singleton")
    def c() -> str:
        return "test"

    def service(a: int, /, b: float, *, c: str) -> Service:
        return Service(ident=f"{a}/{b}/{c}")

    provider = container.register(Service, service, scope="singleton")

    scoped_context = container._get_scoped_context("singleton")

    args, kwargs = scoped_context._get_provider_arguments(provider)

    assert args == [10]
    assert kwargs == {"b": 1.0, "c": "test"}


async def test_async_get_provider_arguments(container: Container) -> None:
    @container.provider(scope="singleton")
    async def a() -> int:
        return 10

    @container.provider(scope="singleton")
    async def b() -> float:
        return 1.0

    @container.provider(scope="singleton")
    async def c() -> str:
        return "test"

    async def service(a: int, /, b: float, *, c: str) -> Service:
        return Service(ident=f"{a}/{b}/{c}")

    provider = container.register(Service, service, scope="singleton")

    scoped_context = container._get_scoped_context("singleton")

    args, kwargs = await scoped_context._aget_provider_arguments(provider)

    assert args == [10]
    assert kwargs == {"b": 1.0, "c": "test"}


def test_inject_missing_annotation(container: Container) -> None:
    def handler(name=dep()) -> str:  # type: ignore[no-untyped-def]
        return name  # type: ignore[no-any-return]

    with pytest.raises(TypeError) as exc_info:
        container.inject(handler)

    assert str(exc_info.value) == (
        "Missing `tests.test_container.test_inject_missing_annotation"
        ".<locals>.handler` parameter `name` annotation."
    )


def test_inject_unknown_dependency_using_strict_mode() -> None:
    container = Container(strict=True)

    def handler(message: str = dep()) -> None:
        pass

    with pytest.raises(LookupError) as exc_info:
        container.inject(handler)

    assert str(exc_info.value) == (
        "`tests.test_container.test_inject_unknown_dependency_using_strict_mode"
        ".<locals>.handler` has an unknown dependency parameter `message` with an "
        "annotation of `str`."
    )


def test_inject(container: Container) -> None:
    @container.provider(scope="singleton")
    def ident_provider() -> str:
        return "1000"

    @container.provider(scope="singleton")
    def service_provider(ident: str) -> Service:
        return Service(ident=ident)

    @container.inject
    def func(name: str, service: Service = dep()) -> str:
        return f"{name} = {service.ident}"

    result = func(name="service ident")

    assert result == "service ident = 1000"


def test_inject_auto_marker(container: Container) -> None:
    @container.provider(scope="singleton")
    def message() -> str:
        return "test"

    @container.inject
    def func(message: str = auto) -> str:
        return message

    result = func()

    assert result == "test"


def test_inject_auto_marker_call(container: Container) -> None:
    @container.provider(scope="singleton")
    def message() -> str:
        return "test"

    @container.inject
    def func(message: str = auto()) -> str:
        return message

    result = func()

    assert result == "test"


def test_inject_class(container: Container) -> None:
    @container.provider(scope="singleton")
    def ident_provider() -> str:
        return "1000"

    @container.provider(scope="singleton")
    def service_provider(ident: str) -> Service:
        return Service(ident=ident)

    @container.inject
    class Handler:
        def __init__(self, name: str, service: Service = dep()) -> None:
            self.name = name
            self.service = service

        def handle(self) -> str:
            return f"{self.name} = {self.service.ident}"

    handler = Handler(name="service ident")

    result = handler.handle()

    assert result == "service ident = 1000"


def test_inject_dataclass(container: Container) -> None:
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
        service: Service = dep()

        def handle(self) -> str:
            return f"{self.name} = {self.service.ident}"

    handler = Handler(name="service ident")

    result = handler.handle()

    assert result == "service ident = 1000"


async def test_inject_with_sync_and_async_resources(container: Container) -> None:
    def ident_provider() -> Iterator[str]:
        yield "1000"

    async def service_provider(ident: str) -> AsyncIterator[Service]:
        yield Service(ident=ident)

    container.register(str, ident_provider, scope="singleton")
    container.register(Service, service_provider, scope="singleton")

    await container.astart()

    @container.inject
    async def func(name: str, service: Service = dep()) -> str:
        return f"{name} = {service.ident}"

    result = await func(name="service ident")

    assert result == "service ident = 1000"


def test_run(container: Container) -> None:
    @container.provider(scope="singleton")
    def value1() -> Annotated[int, "value1"]:
        return 10

    @container.provider(scope="singleton")
    def value2() -> Annotated[int, "value2"]:
        return 20

    def sum_handler(
        value1: int,
        value2: Annotated[int, "value1"] = dep(),
        value3: Annotated[int, "value2"] = dep(),
    ) -> int:
        return value1 + value2 + value3

    result = container.run(sum_handler, value1=30)

    assert result == 60


def test_provider_decorator(container: Container) -> None:
    @container.provider(scope="singleton")
    def ident() -> str:
        return "1000"

    assert container.providers[str] == Provider(obj=ident, scope="singleton")


def test_request_decorator() -> None:
    request(Service)

    assert getattr(Service, "__scope__") == "request"


def test_transient_decorator() -> None:
    transient(Service)

    assert getattr(Service, "__scope__") == "transient"


def test_singleton_decorator() -> None:
    singleton(Service)

    assert getattr(Service, "__scope__") == "singleton"
