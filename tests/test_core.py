import typing as t
import uuid
from dataclasses import dataclass

import pytest
from typing_extensions import Annotated

from pyxdi import Module, Named, Provider, PyxDI, Scope, dep, provider

from tests.fixtures import Service
from tests.scan import ScanModule


@pytest.fixture
def di() -> PyxDI:
    return PyxDI()


# Provider


def test_provider_function_type() -> None:
    provider = Provider(obj=lambda: "test", scope="transient")

    assert provider.is_function
    assert not provider.is_class
    assert not provider.is_generator
    assert not provider.is_async_generator


def test_provider_function_class() -> None:
    provider = Provider(obj=Service, scope="transient")

    assert not provider.is_function
    assert provider.is_class
    assert not provider.is_generator
    assert not provider.is_async_generator


def test_provider_function_resource() -> None:
    def resource() -> t.Iterator[str]:
        yield "test"

    provider = Provider(obj=resource, scope="transient")

    assert not provider.is_function
    assert not provider.is_class
    assert provider.is_generator
    assert not provider.is_async_generator


def test_provider_function_async_resource() -> None:
    async def resource() -> t.AsyncIterator[str]:
        yield "test"

    provider = Provider(obj=resource, scope="transient")

    assert not provider.is_function
    assert not provider.is_class
    assert not provider.is_generator
    assert provider.is_async_generator


def test_provider_name() -> None:
    def obj() -> str:
        return "test"

    provider = Provider(obj=obj, scope="transient")

    assert (
        provider.name
        == str(provider)
        == "tests.test_core.test_provider_name.<locals>.obj"
    )


def test_has_provider(di: PyxDI) -> None:
    di.register_provider(str, lambda: "test", scope="singleton")

    assert di.has_provider(str)


def test_has_no_provider(di: PyxDI) -> None:
    assert not di.has_provider(str)


def test_register_provider(di: PyxDI) -> None:
    def provider_obj() -> str:
        return "test"

    provider = di.register_provider(str, provider_obj, scope="transient")

    assert provider.obj == provider_obj
    assert provider.scope == "transient"


def test_register_provider_already_registered(di: PyxDI) -> None:
    di.register_provider(str, lambda: "test", scope="singleton")

    with pytest.raises(LookupError) as exc_info:
        di.register_provider(str, lambda: "other", scope="singleton")

    assert str(exc_info.value) == "The provider interface `str` already registered."


def test_register_provider_override(di: PyxDI) -> None:
    di.register_provider(str, lambda: "test", scope="singleton")

    def overriden_provider_obj() -> str:
        return "test"

    provider = di.register_provider(
        str, overriden_provider_obj, scope="singleton", override=True
    )

    assert provider.obj == overriden_provider_obj


def test_register_provider_named(di: PyxDI) -> None:
    di.register_provider(
        Annotated[str, Named("msg1")], lambda: "test1", scope="singleton"
    )
    di.register_provider(
        Annotated[str, Named("msg2")], lambda: "test2", scope="singleton"
    )

    assert Annotated[str, Named("msg1")] in di.providers
    assert Annotated[str, Named("msg2")] in di.providers


def test_register_provider_via_constructor() -> None:
    di = PyxDI(
        providers={
            str: Provider(obj=lambda: "test", scope="singleton"),
            int: Provider(obj=lambda: 1, scope="singleton"),
        }
    )

    assert di.get_instance(str) == "test"
    assert di.get_instance(int) == 1


def test_unregister_singleton_scoped_provider(di: PyxDI) -> None:
    di.register_provider(str, lambda: "test", scope="singleton")

    assert str in di.providers

    di.unregister_provider(str)

    assert str not in di.providers


def test_unregister_request_scoped_provider(di: PyxDI) -> None:
    di.register_provider(str, lambda: "test", scope="request")

    assert str in di.providers

    di.unregister_provider(str)

    assert str not in di.providers


def test_unregister_not_registered_provider(di: PyxDI) -> None:
    with pytest.raises(LookupError) as exc_info:
        di.unregister_provider(str)

    assert str(exc_info.value) == "The provider interface `str` not registered."


def test_get_provider(di: PyxDI) -> None:
    provider = di.register_provider(str, lambda: "str", scope="singleton")

    assert di.get_provider(str) == provider


def test_get_provider_not_registered(di: PyxDI) -> None:
    with pytest.raises(LookupError) as exc_info:
        assert di.get_provider(str)

    assert str(exc_info.value) == (
        "The provider interface for `str` has not been registered. Please ensure that "
        "the provider interface is properly registered before attempting to use it."
    )


# Validators


def test_register_provider_invalid_scope(di: PyxDI) -> None:
    with pytest.raises(ValueError) as exc_info:
        di.register_provider(
            str,
            lambda: "test",
            scope="invalid",  # type: ignore[arg-type]
        )

    assert str(exc_info.value) == (
        "The scope provided is invalid. Only the following scopes are supported: "
        "transient, singleton, request. Please use one of the supported scopes when "
        "registering a provider."
    )


def test_register_provider_invalid_transient_resource(di: PyxDI) -> None:
    def provider_obj() -> t.Iterator[str]:
        yield "test"

    with pytest.raises(TypeError) as exc_info:
        di.register_provider(str, provider_obj, scope="transient")

    assert str(exc_info.value) == (
        "The resource provider `tests.test_core"
        ".test_register_provider_invalid_transient_resource.<locals>.provider_obj` is "
        "attempting to register with a transient scope, which is not allowed. Please "
        "update the provider's scope to an appropriate value before registering it."
    )


def test_register_provider_invalid_transient_async_resource(di: PyxDI) -> None:
    async def provider_obj() -> t.AsyncIterator[str]:
        yield "test"

    with pytest.raises(TypeError) as exc_info:
        di.register_provider(str, provider_obj, scope="transient")

    assert str(exc_info.value) == (
        "The resource provider `tests.test_core"
        ".test_register_provider_invalid_transient_async_resource"
        ".<locals>.provider_obj` is attempting to register with a transient scope, "
        "which is not allowed. Please update the provider's scope to an "
        "appropriate value before registering it."
    )


def test_register_provider_valid_resource(di: PyxDI) -> None:
    def provider_obj1() -> t.Iterator[str]:
        yield "test"

    def provider_obj2() -> t.Iterator[int]:
        yield 100

    di.register_provider(str, provider_obj1, scope="singleton")
    di.register_provider(int, provider_obj2, scope="request")


def test_register_provider_valid_async_resource(di: PyxDI) -> None:
    async def provider_obj1() -> t.AsyncIterator[str]:
        yield "test"

    async def provider_obj2() -> t.AsyncIterator[int]:
        yield 100

    di.register_provider(str, provider_obj1, scope="singleton")
    di.register_provider(int, provider_obj2, scope="request")


def test_register_invalid_provider_type(di: PyxDI) -> None:
    with pytest.raises(TypeError) as exc_info:
        di.register_provider(str, "Test", scope="singleton")  # type: ignore[arg-type]

    assert str(exc_info.value) == (
        "The provider `Test` is invalid because it is not a callable object. Only "
        "callable providers are allowed. Please update the provider to a callable "
        "object before attempting to register it."
    )


def test_register_valid_class_provider(di: PyxDI) -> None:
    class Klass:
        pass

    provider = di.register_provider(str, Klass, scope="singleton")

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
    di: PyxDI, scope1: Scope, scope2: Scope, scope3: Scope, valid: bool
) -> None:
    def a() -> int:
        return 2

    def b(a: int) -> float:
        return a * 2.5

    def mixed(a: int, b: float) -> str:
        return f"{a} * {b} = {a * b}"

    try:
        di.register_provider(int, a, scope=scope3)
        di.register_provider(float, b, scope=scope2)
        di.register_provider(str, mixed, scope=scope1)
    except ValueError:
        result = False
    else:
        result = True

    assert result == valid


def test_register_provider_match_scopes_error(di: PyxDI) -> None:
    def provider_int() -> int:
        return 1000

    def provider_str(n: int) -> str:
        return f"{n}"

    di.register_provider(int, provider_int, scope="request")

    with pytest.raises(ValueError) as exc_info:
        di.register_provider(str, provider_str, scope="singleton")

    assert str(exc_info.value) == (
        "The provider `tests.test_core.test_register_provider_match_scopes_error"
        ".<locals>.provider_str` with a singleton scope was attempted to be registered "
        "with the provider `tests.test_core.test_register_provider_match_scopes_error"
        ".<locals>.provider_int` with a `request` scope, which is not allowed. "
        "Please ensure that all providers are registered with matching scopes."
    )


def test_register_provider_without_annotation(di: PyxDI) -> None:
    def service_ident() -> str:
        return "10000"

    def service(ident) -> Service:  # type: ignore[no-untyped-def]
        return Service(ident=ident)

    di.register_provider(str, service_ident, scope="singleton")

    with pytest.raises(TypeError) as exc_info:
        di.register_provider(Service, service, scope="singleton")

    assert str(exc_info.value) == (
        "Missing provider "
        "`tests.test_core.test_register_provider_without_annotation.<locals>.service` "
        "dependency `ident` annotation."
    )


def test_register_provider_with_not_registered_sub_provider(di: PyxDI) -> None:
    def dep2(dep1: int) -> str:
        return str(dep1)

    with pytest.raises(LookupError) as exc_info:
        di.register_provider(str, dep2, scope="singleton")

    assert str(exc_info.value) == (
        "The provider "
        "`tests.test_core.test_register_provider_with_not_registered_sub_provider"
        ".<locals>.dep2` depends on `dep1` of type `int`, which has not been "
        "registered. To resolve this, ensure that `dep1` is registered "
        "before attempting to use it."
    )


def test_register_events(di: PyxDI) -> None:
    events = []

    @di.provider(scope="singleton")
    def message() -> str:
        return "test"

    @di.provider(scope="singleton")
    def event_1(message: str) -> t.Iterator[None]:
        events.append(f"event_1: before {message}")
        yield
        events.append(f"event_1: after {message}")

    @di.provider(scope="singleton")
    def event_2(message: str) -> t.Iterator[None]:
        events.append(f"event_2: before {message}")
        yield
        events.append(f"event_2: after {message}")

    di.start()

    assert events == [
        "event_1: before test",
        "event_2: before test",
    ]

    di.close()

    assert events == [
        "event_1: before test",
        "event_2: before test",
        "event_2: after test",
        "event_1: after test",
    ]


async def test_register_async_events(di: PyxDI) -> None:
    events = []

    @di.provider(scope="singleton")
    def message() -> str:
        return "test"

    @di.provider(scope="singleton")
    async def event_1(message: str) -> t.AsyncIterator[None]:
        events.append(f"event_1: before {message}")
        yield
        events.append(f"event_1: after {message}")

    @di.provider(scope="singleton")
    def event_2(message: str) -> t.Iterator[None]:
        events.append(f"event_2: before {message}")
        yield
        events.append(f"event_2: after {message}")

    await di.astart()

    assert events == [
        "event_1: before test",
        "event_2: before test",
    ]

    await di.aclose()

    assert events == [
        "event_1: before test",
        "event_2: before test",
        "event_2: after test",
        "event_1: after test",
    ]


# Module


class TestModule(Module):
    def configure(self, di: PyxDI) -> None:
        di.register_provider(
            Annotated[str, Named("msg1")], lambda: "Message 1", scope="singleton"
        )

    @provider(scope="singleton")
    def provide_msg2(self) -> Annotated[str, Named("msg2")]:
        return "Message 2"


def test_register_modules() -> None:
    di = PyxDI(modules=[TestModule])

    assert di.has_provider(Annotated[str, Named("msg1")])
    assert di.has_provider(Annotated[str, Named("msg2")])


def test_register_module_class(di: PyxDI) -> None:
    di.register_module(TestModule)

    assert di.has_provider(Annotated[str, Named("msg1")])
    assert di.has_provider(Annotated[str, Named("msg2")])


def test_register_module_instance(di: PyxDI) -> None:
    di.register_module(TestModule())

    assert di.has_provider(Annotated[str, Named("msg1")])
    assert di.has_provider(Annotated[str, Named("msg2")])


def test_register_module_function(di: PyxDI) -> None:
    def configure(di: PyxDI) -> None:
        di.register_provider(str, lambda: "Message 1", scope="singleton")

    di.register_module(configure)

    assert di.has_provider(str)


class OrderedModule(Module):
    @provider(scope="singleton")
    def dep3(self) -> Annotated[str, Named("dep3")]:
        return "dep3"

    @provider(scope="singleton")
    def dep1(self) -> Annotated[str, Named("dep1")]:
        return "dep1"

    @provider(scope="singleton")
    def dep2(self) -> Annotated[str, Named("dep2")]:
        return "dep2"


def test_register_module_ordered_providers(di: PyxDI) -> None:
    di.register_module(OrderedModule)

    assert list(di.providers.keys()) == [
        Annotated[str, Named("dep3")],
        Annotated[str, Named("dep1")],
        Annotated[str, Named("dep2")],
    ]


# Lifespan


def test_start_and_close_singleton_context(di: PyxDI) -> None:
    events = []

    def dep1() -> t.Iterator[str]:
        events.append("dep1:before")
        yield "test"
        events.append("dep1:after")

    di.register_provider(str, dep1, scope="singleton")

    di.start()

    assert di.get_instance(str) == "test"

    di.close()

    assert events == ["dep1:before", "dep1:after"]


def test_request_context(di: PyxDI) -> None:
    events = []

    def dep1() -> t.Iterator[str]:
        events.append("dep1:before")
        yield "test"
        events.append("dep1:after")

    di.register_provider(str, dep1, scope="request")

    with di.request_context():
        assert di.get_instance(str) == "test"

    assert events == ["dep1:before", "dep1:after"]


# Asynchronous lifespan


async def test_astart_and_aclose_singleton_context(di: PyxDI) -> None:
    events = []

    async def dep1() -> t.AsyncIterator[str]:
        events.append("dep1:before")
        yield "test"
        events.append("dep1:after")

    di.register_provider(str, dep1, scope="singleton")

    await di.astart()

    assert di.get_instance(str) == "test"

    await di.aclose()

    assert events == ["dep1:before", "dep1:after"]


async def test_arequest_context(di: PyxDI) -> None:
    events = []

    async def dep1() -> t.AsyncIterator[str]:
        events.append("dep1:before")
        yield "test"
        events.append("dep1:after")

    di.register_provider(str, dep1, scope="request")

    async with di.arequest_context():
        assert await di.aget_instance(str) == "test"

    assert events == ["dep1:before", "dep1:after"]


def test_reset_resolved_instances(di: PyxDI) -> None:
    di.register_provider(str, lambda: "test", scope="singleton")
    di.register_provider(int, lambda: 1, scope="singleton")

    di.get_instance(str)
    di.get_instance(int)

    assert di.has_instance(str)
    assert di.has_instance(int)

    di.reset()

    assert not di.has_instance(str)
    assert not di.has_instance(int)


# Instance


def test_get_singleton_scoped(di: PyxDI) -> None:
    instance = "test"

    di.register_provider(str, lambda: instance, scope="singleton")

    assert di.get_instance(str) == instance


def test_get_singleton_scoped_not_started(di: PyxDI) -> None:
    @di.provider(scope="singleton")
    def message() -> t.Iterator[str]:
        yield "test"

    assert di.get_instance(str) == "test"


def test_get_singleton_scoped_resource(di: PyxDI) -> None:
    instance = "test"

    def provide() -> t.Iterator[str]:
        yield instance

    di.register_provider(str, provide, scope="singleton")
    di.start()

    assert di.get_instance(str) == instance


def test_get_singleton_scoped_started_with_async_resource_provider(di: PyxDI) -> None:
    instance = "test"

    async def provide() -> t.AsyncIterator[str]:
        yield instance

    di.register_provider(str, provide, scope="singleton")

    with pytest.raises(TypeError) as exc_info:
        di.start()

    assert str(exc_info.value) == (
        "The provider `tests.test_core.test_get_singleton_scoped_started_with_"
        "async_resource_provider.<locals>.provide` cannot be started in synchronous "
        "mode because it is an asynchronous provider. Please start the provider "
        "in asynchronous mode before using it."
    )


def test_get(di: PyxDI) -> None:
    instance = "test"

    def provide() -> t.Iterator[str]:
        yield instance

    di.register_provider(str, provide, scope="singleton")

    di.get_instance(str)


async def test_get_singleton_scoped_async_resource(di: PyxDI) -> None:
    instance = "test"

    def provide() -> t.Iterator[str]:
        yield instance

    di.register_provider(str, provide, scope="singleton")

    await di.astart()

    assert di.get_instance(str) == instance


async def test_get_singleton_scoped_async_and_sync_resources(di: PyxDI) -> None:
    instance_str = "test"
    instance_int = 100

    def provider_1() -> t.Iterator[str]:
        yield instance_str

    async def provider_2() -> t.AsyncIterator[int]:
        yield instance_int

    di.register_provider(str, provider_1, scope="singleton")
    di.register_provider(int, provider_2, scope="singleton")

    await di.astart()

    assert di.get_instance(str) == instance_str
    assert di.get_instance(int) == instance_int


async def test_get_singleton_scoped_async_resource_not_started(di: PyxDI) -> None:
    instance = "test"

    async def provide() -> t.AsyncIterator[str]:
        yield instance

    di.register_provider(str, provide, scope="singleton")

    with pytest.raises(TypeError) as exc_info:
        di.get_instance(str)

    assert str(exc_info.value) == (
        "The provider `tests.test_core"
        ".test_get_singleton_scoped_async_resource_not_started.<locals>.provide` "
        "cannot be started in synchronous mode because it is an asynchronous provider. "
        "Please start the provider in asynchronous mode before using it."
    )


def test_get_request_scoped(di: PyxDI) -> None:
    instance = "test"

    di.register_provider(str, lambda: instance, scope="request")

    with di.request_context():
        assert di.get_instance(str) == instance


def test_get_request_scoped_not_started(di: PyxDI) -> None:
    instance = "test"

    di.register_provider(str, lambda: instance, scope="request")

    with pytest.raises(LookupError) as exc_info:
        assert di.get_instance(str)

    assert str(exc_info.value) == (
        "The request context has not been started. Please ensure that the request "
        "context is properly initialized before attempting to use it."
    )


def test_get_transient_scoped(di: PyxDI) -> None:
    di.register_provider(uuid.UUID, uuid.uuid4, scope="transient")

    assert di.get_instance(uuid.UUID) != di.get_instance(uuid.UUID)


def test_get_async_transient_scoped(di: PyxDI) -> None:
    @di.provider(scope="transient")
    async def get_uuid() -> uuid.UUID:
        return uuid.uuid4()

    with pytest.raises(TypeError) as exc_info:
        di.get_instance(uuid.UUID)

    assert str(exc_info.value) == (
        "The instance for the coroutine provider "
        "`tests.test_core.test_get_async_transient_scoped.<locals>.get_uuid` "
        "cannot be created in synchronous mode."
    )


async def test_async_get_transient_scoped(di: PyxDI) -> None:
    @di.provider(scope="transient")
    async def get_uuid() -> uuid.UUID:
        return uuid.uuid4()

    assert await di.aget_instance(uuid.UUID) != await di.aget_instance(uuid.UUID)


async def test_async_get_synchronous_resource(di: PyxDI) -> None:
    @di.provider(scope="singleton")
    def msg() -> t.Iterator[str]:
        yield "test"

    assert await di.aget_instance(str) == "test"


def test_get_not_registered_instance(di: PyxDI) -> None:
    with pytest.raises(Exception) as exc_info:
        di.get_instance(str)

    assert str(exc_info.value) == (
        "The provider interface for `str` has not been registered. Please ensure that "
        "the provider interface is properly registered before attempting to use it."
    )


def test_has_instance(di: PyxDI) -> None:
    assert not di.has_instance(str)


def test_reset_instance(di: PyxDI) -> None:
    di.register_provider(str, lambda: "test", scope="singleton")
    di.get_instance(str)

    assert di.has_instance(str)

    di.reset_instance(str)

    assert not di.has_instance(str)


def test_override(di: PyxDI) -> None:
    origin_name = "origin"
    overriden_name = "overriden"

    @di.provider(scope="singleton")
    def name() -> str:
        return origin_name

    with di.override(str, overriden_name):
        assert di.get_instance(str) == overriden_name

    assert di.get_instance(str) == origin_name


def test_override_provider_not_registered(di: PyxDI) -> None:
    with pytest.raises(LookupError) as exc_info:
        with di.override(str, "test"):
            pass

    assert str(exc_info.value) == "The provider interface `str` not registered."


def test_override_transient_provider(di: PyxDI) -> None:
    overriden_uuid = uuid.uuid4()

    @di.provider(scope="transient")
    def uuid_provider() -> uuid.UUID:
        return uuid.uuid4()

    with di.override(uuid.UUID, overriden_uuid):
        assert di.get_instance(uuid.UUID) == overriden_uuid

    assert di.get_instance(uuid.UUID) != overriden_uuid


def test_override_resource_provider(di: PyxDI) -> None:
    origin = "origin"
    overriden = "overriden"

    @di.provider(scope="singleton")
    def message() -> t.Iterator[str]:
        yield origin

    with di.override(str, overriden):
        assert di.get_instance(str) == overriden

    assert di.get_instance(str) == origin


async def test_override_async_resource_provider(di: PyxDI) -> None:
    origin = "origin"
    overriden = "overriden"

    @di.provider(scope="singleton")
    async def message() -> t.AsyncIterator[str]:
        yield origin

    with di.override(str, overriden):
        assert di.get_instance(str) == overriden


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
    di: PyxDI, annotation: t.Type[t.Any], expected: t.Type[t.Any]
) -> None:
    def provider() -> annotation:  # type: ignore[valid-type]
        return object()

    assert di._get_provider_annotation(provider) == expected


def test_get_provider_annotation_missing(di: PyxDI) -> None:
    def provider():  # type: ignore[no-untyped-def]
        return object()

    with pytest.raises(TypeError) as exc_info:
        di._get_provider_annotation(provider)

    assert str(exc_info.value) == (
        "Missing `tests.test_core.test_get_provider_annotation_missing.<locals>"
        ".provider` provider return annotation."
    )


def test_get_provider_annotation_origin_without_args(di: PyxDI) -> None:
    def provider() -> list:  # type: ignore[type-arg]
        return []

    with pytest.raises(TypeError) as exc_info:
        di._get_provider_annotation(provider)

    assert str(exc_info.value) == (
        "Cannot use `tests.test_core.test_get_provider_annotation_origin_without_args."
        "<locals>.provider` generic type annotation without actual type."
    )


def test_get_provider_arguments(di: PyxDI) -> None:
    @di.provider(scope="singleton")
    def a() -> int:
        return 10

    @di.provider(scope="singleton")
    def b() -> float:
        return 1.0

    @di.provider(scope="singleton")
    def c() -> str:
        return "test"

    def service(a: int, /, b: float, *, c: str) -> Service:
        return Service(ident=f"{a}/{b}/{c}")

    provider = di.register_provider(Service, service, scope="singleton")

    args, kwargs = di._get_provider_arguments(provider)

    assert args == [10]
    assert kwargs == {"b": 1.0, "c": "test"}


async def test_async_get_provider_arguments(di: PyxDI) -> None:
    @di.provider(scope="singleton")
    async def a() -> int:
        return 10

    @di.provider(scope="singleton")
    async def b() -> float:
        return 1.0

    @di.provider(scope="singleton")
    async def c() -> str:
        return "test"

    async def service(a: int, /, b: float, *, c: str) -> Service:
        return Service(ident=f"{a}/{b}/{c}")

    provider = di.register_provider(Service, service, scope="singleton")

    args, kwargs = await di._aget_provider_arguments(provider)

    assert args == [10]
    assert kwargs == {"b": 1.0, "c": "test"}


def test_inject_missing_annotation(di: PyxDI) -> None:
    def handler(name=dep) -> str:  # type: ignore[no-untyped-def]
        return name  # type: ignore[no-any-return]

    with pytest.raises(TypeError) as exc_info:
        di.inject(handler)

    assert str(exc_info.value) == (
        "Missing `tests.test_core.test_inject_missing_annotation.<locals>.handler` "
        "parameter `name` annotation."
    )


def test_inject_unknown_dependency(di: PyxDI) -> None:
    def handler(message: str = dep) -> None:
        pass

    with pytest.raises(TypeError) as exc_info:
        di.inject(handler)

    assert str(exc_info.value) == (
        "`tests.test_core.test_inject_unknown_dependency.<locals>.handler` "
        "has an unknown dependency parameter `message` with an annotation of `str`."
    )


def test_inject(di: PyxDI) -> None:
    @di.provider(scope="singleton")
    def ident_provider() -> str:
        return "1000"

    @di.provider(scope="singleton")
    def service_provider(ident: str) -> Service:
        return Service(ident=ident)

    @di.inject
    def func(name: str, service: Service = dep) -> str:
        return f"{name} = {service.ident}"

    result = func(name="service ident")

    assert result == "service ident = 1000"


def test_inject_class(di: PyxDI) -> None:
    @di.provider(scope="singleton")
    def ident_provider() -> str:
        return "1000"

    @di.provider(scope="singleton")
    def service_provider(ident: str) -> Service:
        return Service(ident=ident)

    @di.inject
    class Handler:
        def __init__(self, name: str, service: Service = dep) -> None:
            self.name = name
            self.service = service

        def handle(self) -> str:
            return f"{self.name} = {self.service.ident}"

    handler = Handler(name="service ident")

    result = handler.handle()

    assert result == "service ident = 1000"


def test_inject_dataclass(di: PyxDI) -> None:
    @di.provider(scope="singleton")
    def ident_provider() -> str:
        return "1000"

    @di.provider(scope="singleton")
    def service_provider(ident: str) -> Service:
        return Service(ident=ident)

    @di.inject
    @dataclass
    class Handler:
        name: str
        service: Service = dep

        def handle(self) -> str:
            return f"{self.name} = {self.service.ident}"

    handler = Handler(name="service ident")

    result = handler.handle()

    assert result == "service ident = 1000"


async def test_inject_with_sync_and_async_resources(di: PyxDI) -> None:
    def ident_provider() -> t.Iterator[str]:
        yield "1000"

    async def service_provider(ident: str) -> t.AsyncIterator[Service]:
        yield Service(ident=ident)

    di.register_provider(str, ident_provider, scope="singleton")
    di.register_provider(Service, service_provider, scope="singleton")

    await di.astart()

    @di.inject
    async def func(name: str, service: Service = dep) -> str:
        return f"{name} = {service.ident}"

    result = await func(name="service ident")

    assert result == "service ident = 1000"


def test_provider_decorator(di: PyxDI) -> None:
    @di.provider(scope="singleton")
    def ident() -> str:
        return "1000"

    assert di.get_provider(str) == Provider(obj=ident, scope="singleton")


# Scanner


def test_scan(di: PyxDI) -> None:
    di.register_module(ScanModule)
    di.scan(["tests.scan"])

    from .scan.a.a3.handlers import a_a3_handler_1, a_a3_handler_2

    assert a_a3_handler_1() == "a.a1.str_provider"
    assert a_a3_handler_2().ident == "a.a1.str_provider"


def test_scan_single_package(di: PyxDI) -> None:
    di.register_module(ScanModule)
    di.scan("tests.scan.a.a3.handlers")

    from .scan.a.a3.handlers import a_a3_handler_1

    assert a_a3_handler_1() == "a.a1.str_provider"


def test_scan_non_existing_tag(di: PyxDI) -> None:
    di.scan(["tests.scan"], tags=["non_existing_tag"])

    assert not di.providers


def test_scan_tagged(di: PyxDI) -> None:
    di.register_module(ScanModule)
    di.scan(["tests.scan.a"], tags=["inject"])

    from .scan.a.a3.handlers import a_a3_handler_1

    assert a_a3_handler_1() == "a.a1.str_provider"
