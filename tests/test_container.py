import logging
import typing as t
import uuid
from dataclasses import dataclass

import pytest
from typing_extensions import Annotated

from pyxdi import (
    Container,
    Provider,
    Scope,
    auto,
    request,
    singleton,
    transient,
)

from tests.fixtures import Service


@pytest.fixture
def container() -> Container:
    return Container()


# Root


def test_default_strict(container: Container) -> None:
    assert container.strict


def test_has_provider(container: Container) -> None:
    container.register_provider(str, lambda: "test", scope="singleton")

    assert container.has_provider(str)


def test_has_no_provider(container: Container) -> None:
    assert not container.has_provider(str)


def test_register_provider(container: Container) -> None:
    def provider_obj() -> str:
        return "test"

    provider = container.register_provider(str, provider_obj, scope="transient")

    assert provider.obj == provider_obj
    assert provider.scope == "transient"


def test_register_provider_already_registered(container: Container) -> None:
    container.register_provider(str, lambda: "test", scope="singleton")

    with pytest.raises(LookupError) as exc_info:
        container.register_provider(str, lambda: "other", scope="singleton")

    assert str(exc_info.value) == "The provider interface `str` already registered."


def test_register_provider_override(container: Container) -> None:
    container.register_provider(str, lambda: "test", scope="singleton")

    def overriden_provider_obj() -> str:
        return "test"

    provider = container.register_provider(
        str, overriden_provider_obj, scope="singleton", override=True
    )

    assert provider.obj == overriden_provider_obj


def test_register_provider_named(container: Container) -> None:
    container.register_provider(
        Annotated[str, "msg1"],
        lambda: "test1",
        scope="singleton",
    )
    container.register_provider(
        Annotated[str, "msg2"],
        lambda: "test2",
        scope="singleton",
    )

    assert Annotated[str, "msg1"] in container.providers
    assert Annotated[str, "msg2"] in container.providers


def test_register_provider_via_constructor() -> None:
    container = Container(
        providers={
            str: Provider(obj=lambda: "test", scope="singleton"),
            int: Provider(obj=lambda: 1, scope="singleton"),
        }
    )

    assert container.get_instance(str) == "test"
    assert container.get_instance(int) == 1


def test_unregister_singleton_scoped_provider(container: Container) -> None:
    container.register_provider(str, lambda: "test", scope="singleton")

    assert str in container.providers

    container.unregister_provider(str)

    assert str not in container.providers


def test_unregister_request_scoped_provider(container: Container) -> None:
    container.register_provider(str, lambda: "test", scope="request")

    assert str in container.providers

    container.unregister_provider(str)

    assert str not in container.providers


def test_unregister_not_registered_provider(container: Container) -> None:
    with pytest.raises(LookupError) as exc_info:
        container.unregister_provider(str)

    assert str(exc_info.value) == "The provider interface `str` not registered."


def test_get_provider(container: Container) -> None:
    provider = container.register_provider(str, lambda: "str", scope="singleton")

    assert container.get_provider(str) == provider


def test_get_provider_not_registered(container: Container) -> None:
    with pytest.raises(LookupError) as exc_info:
        assert container.get_provider(str)

    assert str(exc_info.value) == (
        "The provider interface for `str` has not been registered. Please ensure that "
        "the provider interface is properly registered before attempting to use it."
    )


# Auto register


def test_get_auto_registered_provider_scope_defined() -> None:
    container = Container(strict=False)

    class Service:
        __scope__ = "singleton"

    assert container.get_provider(Service).scope == "singleton"


def test_get_auto_registered_provider_scope_from_sub_provider_request() -> None:
    container = Container(strict=False)

    @container.provider(scope="request")
    def message() -> str:
        return "test"

    @dataclass
    class Service:
        message: str

    with container.request_context():
        _ = container.get_instance(Service)

    assert container.get_provider(Service).scope == "request"


def test_get_auto_registered_provider_scope_from_sub_provider_transient() -> None:
    container = Container(strict=False)

    @container.provider(scope="transient")
    def uuid_generator() -> Annotated[str, "uuid_generator"]:
        return str(uuid.uuid4())

    @dataclass
    class Entity:
        id: Annotated[str, "uuid_generator"]

    _ = container.get_instance(Entity)

    assert container.get_provider(Entity).scope == "transient"


def test_get_auto_registered_nested_singleton_provider() -> None:
    container = Container(strict=False)

    @dataclass
    class Repository:
        __scope__ = "singleton"

    @dataclass
    class Service:
        repository: Repository

    with container.request_context():
        _ = container.get_instance(Service)

    assert container.get_provider(Service).scope == "singleton"


def test_get_auto_registered_missing_scope() -> None:
    container = Container(strict=False)

    @dataclass
    class Repository:
        pass

    @dataclass
    class Service:
        repository: Repository

    with pytest.raises(TypeError) as exc_info:
        _ = container.get_instance(Service)

    assert str(exc_info.value) == (
        "Unable to automatically register the provider interface for "
        "`tests.test_container.test_get_auto_registered_missing_scope.<locals>"
        ".Repository` because the scope detection failed. Please resolve "
        "this issue by using the appropriate scope decorator."
    )


def test_get_auto_registered_with_primitive_class() -> None:
    container = Container(strict=False)

    @dataclass
    class Service:
        name: str

    with pytest.raises(LookupError) as exc_info:
        _ = container.get_instance(Service).name

    assert str(exc_info.value) == (
        "The provider interface for `str` has not been registered. "
        "Please ensure that the provider interface is properly registered "
        "before attempting to use it."
    )


def test_inject_auto_registered_log_message(caplog: pytest.LogCaptureFixture) -> None:
    class Service:
        pass

    container = Container(strict=False)

    with caplog.at_level(logging.DEBUG, logger="pyxdi"):

        @container.inject
        def handler(service: Service = auto()) -> None:
            pass

        assert caplog.messages == [
            "Cannot validate the `tests.test_container"
            ".test_inject_auto_registered_log_message.<locals>.handler` parameter "
            "`service` with an annotation of `tests.test_container"
            ".test_inject_auto_registered_log_message.<locals>.Service due to being "
            "in non-strict mode. It will be validated at the first call."
        ]


# Validators


def test_register_provider_invalid_scope(container: Container) -> None:
    with pytest.raises(ValueError) as exc_info:
        container.register_provider(
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
    def provider_obj() -> t.Iterator[str]:
        yield "test"

    with pytest.raises(TypeError) as exc_info:
        container.register_provider(str, provider_obj, scope="transient")

    assert str(exc_info.value) == (
        "The resource provider `tests.test_container"
        ".test_register_provider_invalid_transient_resource.<locals>.provider_obj` is "
        "attempting to register with a transient scope, which is not allowed. Please "
        "update the provider's scope to an appropriate value before registering it."
    )


def test_register_provider_invalid_transient_async_resource(
    container: Container,
) -> None:
    async def provider_obj() -> t.AsyncIterator[str]:
        yield "test"

    with pytest.raises(TypeError) as exc_info:
        container.register_provider(str, provider_obj, scope="transient")

    assert str(exc_info.value) == (
        "The resource provider `tests.test_container"
        ".test_register_provider_invalid_transient_async_resource"
        ".<locals>.provider_obj` is attempting to register with a transient scope, "
        "which is not allowed. Please update the provider's scope to an "
        "appropriate value before registering it."
    )


def test_register_provider_valid_resource(container: Container) -> None:
    def provider_obj1() -> t.Iterator[str]:
        yield "test"

    def provider_obj2() -> t.Iterator[int]:
        yield 100

    container.register_provider(str, provider_obj1, scope="singleton")
    container.register_provider(int, provider_obj2, scope="request")


def test_register_provider_valid_async_resource(container: Container) -> None:
    async def provider_obj1() -> t.AsyncIterator[str]:
        yield "test"

    async def provider_obj2() -> t.AsyncIterator[int]:
        yield 100

    container.register_provider(str, provider_obj1, scope="singleton")
    container.register_provider(int, provider_obj2, scope="request")


def test_register_invalid_provider_type(container: Container) -> None:
    with pytest.raises(TypeError) as exc_info:
        container.register_provider(str, "Test", scope="singleton")  # type: ignore[arg-type]

    assert str(exc_info.value) == (
        "The provider `Test` is invalid because it is not a callable object. Only "
        "callable providers are allowed. Please update the provider to a callable "
        "object before attempting to register it."
    )


def test_register_valid_class_provider(container: Container) -> None:
    class Klass:
        pass

    provider = container.register_provider(str, Klass, scope="singleton")

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
        container.register_provider(int, a, scope=scope3)
        container.register_provider(float, b, scope=scope2)
        container.register_provider(str, mixed, scope=scope1)
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

    container.register_provider(int, provider_int, scope="request")

    with pytest.raises(ValueError) as exc_info:
        container.register_provider(str, provider_str, scope="singleton")

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

    container.register_provider(str, service_ident, scope="singleton")

    with pytest.raises(TypeError) as exc_info:
        container.register_provider(Service, service, scope="singleton")

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

    with pytest.raises(LookupError) as exc_info:
        container.register_provider(str, dep2, scope="singleton")

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
    def event_1(message: str) -> t.Iterator[None]:
        events.append(f"event_1: before {message}")
        yield
        events.append(f"event_1: after {message}")

    @container.provider(scope="singleton")
    def event_2(message: str) -> t.Iterator[None]:
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
    async def event_1(message: str) -> t.AsyncIterator[None]:
        events.append(f"event_1: before {message}")
        yield
        events.append(f"event_1: after {message}")

    @container.provider(scope="singleton")
    def event_2(message: str) -> t.Iterator[None]:
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


# Lifespan


def test_start_and_close_singleton_context(container: Container) -> None:
    events = []

    def dep1() -> t.Iterator[str]:
        events.append("dep1:before")
        yield "test"
        events.append("dep1:after")

    container.register_provider(str, dep1, scope="singleton")

    container.start()

    assert container.get_instance(str) == "test"

    container.close()

    assert events == ["dep1:before", "dep1:after"]


def test_request_context(container: Container) -> None:
    events = []

    def dep1() -> t.Iterator[str]:
        events.append("dep1:before")
        yield "test"
        events.append("dep1:after")

    container.register_provider(str, dep1, scope="request")

    with container.request_context():
        assert container.get_instance(str) == "test"

    assert events == ["dep1:before", "dep1:after"]


# Asynchronous lifespan


async def test_astart_and_aclose_singleton_context(container: Container) -> None:
    events = []

    async def dep1() -> t.AsyncIterator[str]:
        events.append("dep1:before")
        yield "test"
        events.append("dep1:after")

    container.register_provider(str, dep1, scope="singleton")

    await container.astart()

    assert container.get_instance(str) == "test"

    await container.aclose()

    assert events == ["dep1:before", "dep1:after"]


async def test_arequest_context(container: Container) -> None:
    events = []

    async def dep1() -> t.AsyncIterator[str]:
        events.append("dep1:before")
        yield "test"
        events.append("dep1:after")

    container.register_provider(str, dep1, scope="request")

    async with container.arequest_context():
        assert await container.aget_instance(str) == "test"

    assert events == ["dep1:before", "dep1:after"]


def test_reset_resolved_instances(container: Container) -> None:
    container.register_provider(str, lambda: "test", scope="singleton")
    container.register_provider(int, lambda: 1, scope="singleton")

    container.get_instance(str)
    container.get_instance(int)

    assert container.has_instance(str)
    assert container.has_instance(int)

    container.reset()

    assert not container.has_instance(str)
    assert not container.has_instance(int)


# Instance


def test_get_singleton_scoped(container: Container) -> None:
    instance = "test"

    container.register_provider(str, lambda: instance, scope="singleton")

    assert container.get_instance(str) == instance


def test_get_singleton_scoped_not_started(container: Container) -> None:
    @container.provider(scope="singleton")
    def message() -> t.Iterator[str]:
        yield "test"

    assert container.get_instance(str) == "test"


def test_get_singleton_scoped_resource(container: Container) -> None:
    instance = "test"

    def provide() -> t.Iterator[str]:
        yield instance

    container.register_provider(str, provide, scope="singleton")
    container.start()

    assert container.get_instance(str) == instance


def test_get_singleton_scoped_started_with_async_resource_provider(
    container: Container,
) -> None:
    instance = "test"

    async def provide() -> t.AsyncIterator[str]:
        yield instance

    container.register_provider(str, provide, scope="singleton")

    with pytest.raises(TypeError) as exc_info:
        container.start()

    assert str(exc_info.value) == (
        "The provider `tests.test_container.test_get_singleton_scoped_started_with_"
        "async_resource_provider.<locals>.provide` cannot be started in synchronous "
        "mode because it is an asynchronous provider. Please start the provider "
        "in asynchronous mode before using it."
    )


def test_get(container: Container) -> None:
    instance = "test"

    def provide() -> t.Iterator[str]:
        yield instance

    container.register_provider(str, provide, scope="singleton")

    container.get_instance(str)


async def test_get_singleton_scoped_async_resource(container: Container) -> None:
    instance = "test"

    def provide() -> t.Iterator[str]:
        yield instance

    container.register_provider(str, provide, scope="singleton")

    await container.astart()

    assert container.get_instance(str) == instance


async def test_get_singleton_scoped_async_and_sync_resources(
    container: Container,
) -> None:
    instance_str = "test"
    instance_int = 100

    def provider_1() -> t.Iterator[str]:
        yield instance_str

    async def provider_2() -> t.AsyncIterator[int]:
        yield instance_int

    container.register_provider(str, provider_1, scope="singleton")
    container.register_provider(int, provider_2, scope="singleton")

    await container.astart()

    assert container.get_instance(str) == instance_str
    assert container.get_instance(int) == instance_int


async def test_get_singleton_scoped_async_resource_not_started(
    container: Container,
) -> None:
    instance = "test"

    async def provide() -> t.AsyncIterator[str]:
        yield instance

    container.register_provider(str, provide, scope="singleton")

    with pytest.raises(TypeError) as exc_info:
        container.get_instance(str)

    assert str(exc_info.value) == (
        "The provider `tests.test_container"
        ".test_get_singleton_scoped_async_resource_not_started.<locals>.provide` "
        "cannot be started in synchronous mode because it is an asynchronous provider. "
        "Please start the provider in asynchronous mode before using it."
    )


def test_get_request_scoped(container: Container) -> None:
    instance = "test"

    container.register_provider(str, lambda: instance, scope="request")

    with container.request_context():
        assert container.get_instance(str) == instance


def test_get_request_scoped_not_started(container: Container) -> None:
    instance = "test"

    container.register_provider(str, lambda: instance, scope="request")

    with pytest.raises(LookupError) as exc_info:
        assert container.get_instance(str)

    assert str(exc_info.value) == (
        "The request context has not been started. Please ensure that the request "
        "context is properly initialized before attempting to use it."
    )


def test_get_transient_scoped(container: Container) -> None:
    container.register_provider(uuid.UUID, uuid.uuid4, scope="transient")

    assert container.get_instance(uuid.UUID) != container.get_instance(uuid.UUID)


def test_get_async_transient_scoped(container: Container) -> None:
    @container.provider(scope="transient")
    async def get_uuid() -> uuid.UUID:
        return uuid.uuid4()

    with pytest.raises(TypeError) as exc_info:
        container.get_instance(uuid.UUID)

    assert str(exc_info.value) == (
        "The instance for the coroutine provider "
        "`tests.test_container.test_get_async_transient_scoped.<locals>.get_uuid` "
        "cannot be created in synchronous mode."
    )


async def test_async_get_transient_scoped(container: Container) -> None:
    @container.provider(scope="transient")
    async def get_uuid() -> uuid.UUID:
        return uuid.uuid4()

    assert await container.aget_instance(uuid.UUID) != await container.aget_instance(
        uuid.UUID
    )


async def test_async_get_synchronous_resource(container: Container) -> None:
    @container.provider(scope="singleton")
    def msg() -> t.Iterator[str]:
        yield "test"

    assert await container.aget_instance(str) == "test"


def test_get_not_registered_instance(container: Container) -> None:
    with pytest.raises(Exception) as exc_info:
        container.get_instance(str)

    assert str(exc_info.value) == (
        "The provider interface for `str` has not been registered. Please ensure that "
        "the provider interface is properly registered before attempting to use it."
    )


def test_has_instance(container: Container) -> None:
    assert not container.has_instance(str)


def test_reset_instance(container: Container) -> None:
    container.register_provider(str, lambda: "test", scope="singleton")
    container.get_instance(str)

    assert container.has_instance(str)

    container.reset_instance(str)

    assert not container.has_instance(str)


def test_override(container: Container) -> None:
    origin_name = "origin"
    overriden_name = "overriden"

    @container.provider(scope="singleton")
    def name() -> str:
        return origin_name

    with container.override(str, overriden_name):
        assert container.get_instance(str) == overriden_name

    assert container.get_instance(str) == origin_name


def test_override_provider_not_registered(container: Container) -> None:
    with pytest.raises(LookupError) as exc_info:
        with container.override(str, "test"):
            pass

    assert str(exc_info.value) == "The provider interface `str` not registered."


def test_override_transient_provider(container: Container) -> None:
    overriden_uuid = uuid.uuid4()

    @container.provider(scope="transient")
    def uuid_provider() -> uuid.UUID:
        return uuid.uuid4()

    with container.override(uuid.UUID, overriden_uuid):
        assert container.get_instance(uuid.UUID) == overriden_uuid

    assert container.get_instance(uuid.UUID) != overriden_uuid


def test_override_resource_provider(container: Container) -> None:
    origin = "origin"
    overriden = "overriden"

    @container.provider(scope="singleton")
    def message() -> t.Iterator[str]:
        yield origin

    with container.override(str, overriden):
        assert container.get_instance(str) == overriden

    assert container.get_instance(str) == origin


async def test_override_async_resource_provider(container: Container) -> None:
    origin = "origin"
    overriden = "overriden"

    @container.provider(scope="singleton")
    async def message() -> t.AsyncIterator[str]:
        yield origin

    with container.override(str, overriden):
        assert container.get_instance(str) == overriden


# Inspections


@pytest.mark.parametrize(
    "annotation, expected",
    [
        (str, str),
        (int, int),
        (Service, Service),
        (t.Iterator[Service], Service),
        (t.AsyncIterator[Service], Service),
        (t.Dict[str, t.Any], t.Dict[str, t.Any]),
        (t.List[str], t.List[str]),
        (t.Tuple[str, ...], t.Tuple[str, ...]),
    ],
)
def test_get_supported_provider_annotation(
    container: Container, annotation: t.Type[t.Any], expected: t.Type[t.Any]
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


def test_get_provider_annotation_origin_without_args(container: Container) -> None:
    def provider() -> list:  # type: ignore[type-arg]
        return []

    with pytest.raises(TypeError) as exc_info:
        container._get_provider_annotation(provider)

    assert str(exc_info.value) == (
        "Cannot use `tests.test_container"
        ".test_get_provider_annotation_origin_without_args.<locals>.provider` generic "
        "type annotation without actual type."
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

    provider = container.register_provider(Service, service, scope="singleton")

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

    provider = container.register_provider(Service, service, scope="singleton")

    scoped_context = container._get_scoped_context("singleton")

    args, kwargs = await scoped_context._aget_provider_arguments(provider)

    assert args == [10]
    assert kwargs == {"b": 1.0, "c": "test"}


def test_inject_missing_annotation(container: Container) -> None:
    def handler(name=auto()) -> str:  # type: ignore[no-untyped-def]
        return name  # type: ignore[no-any-return]

    with pytest.raises(TypeError) as exc_info:
        container.inject(handler)

    assert str(exc_info.value) == (
        "Missing `tests.test_container.test_inject_missing_annotation"
        ".<locals>.handler` parameter `name` annotation."
    )


def test_inject_unknown_dependency(container: Container) -> None:
    def handler(message: str = auto()) -> None:
        pass

    with pytest.raises(LookupError) as exc_info:
        container.inject(handler)

    assert str(exc_info.value) == (
        "`tests.test_container.test_inject_unknown_dependency.<locals>.handler` "
        "has an unknown dependency parameter `message` with an annotation of `str`."
    )


def test_inject(container: Container) -> None:
    @container.provider(scope="singleton")
    def ident_provider() -> str:
        return "1000"

    @container.provider(scope="singleton")
    def service_provider(ident: str) -> Service:
        return Service(ident=ident)

    @container.inject
    def func(name: str, service: Service = auto()) -> str:
        return f"{name} = {service.ident}"

    result = func(name="service ident")

    assert result == "service ident = 1000"


def test_inject_class(container: Container) -> None:
    @container.provider(scope="singleton")
    def ident_provider() -> str:
        return "1000"

    @container.provider(scope="singleton")
    def service_provider(ident: str) -> Service:
        return Service(ident=ident)

    @container.inject
    class Handler:
        def __init__(self, name: str, service: Service = auto()) -> None:
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
        service: Service = auto()

        def handle(self) -> str:
            return f"{self.name} = {self.service.ident}"

    handler = Handler(name="service ident")

    result = handler.handle()

    assert result == "service ident = 1000"


async def test_inject_with_sync_and_async_resources(container: Container) -> None:
    def ident_provider() -> t.Iterator[str]:
        yield "1000"

    async def service_provider(ident: str) -> t.AsyncIterator[Service]:
        yield Service(ident=ident)

    container.register_provider(str, ident_provider, scope="singleton")
    container.register_provider(Service, service_provider, scope="singleton")

    await container.astart()

    @container.inject
    async def func(name: str, service: Service = auto()) -> str:
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
        value2: Annotated[int, "value1"] = auto(),
        value3: Annotated[int, "value2"] = auto(),
    ) -> int:
        return value1 + value2 + value3

    result = container.run(sum_handler, value1=30)

    assert result == 60


def test_provider_decorator(container: Container) -> None:
    @container.provider(scope="singleton")
    def ident() -> str:
        return "1000"

    assert container.get_provider(str) == Provider(obj=ident, scope="singleton")


def test_request_decorator() -> None:
    request(Service)

    assert getattr(Service, "__scope__") == "request"


def test_transient_decorator() -> None:
    transient(Service)

    assert getattr(Service, "__scope__") == "transient"


def test_singleton_decorator() -> None:
    singleton(Service)

    assert getattr(Service, "__scope__") == "singleton"
