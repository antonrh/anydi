import typing as t
import uuid
from dataclasses import dataclass

import pytest
from typing_extensions import Annotated

from pyxdi import provider
from pyxdi.core import Module, Provider, PyxDI, Scope, dep, named
from pyxdi.exceptions import (
    AnnotationError,
    InvalidScopeError,
    ProviderError,
    ScopeMismatchError,
    UnknownDependencyError,
)

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
    assert not provider.is_resource
    assert not provider.is_async_resource


def test_provider_function_class() -> None:
    provider = Provider(obj=Service, scope="transient")

    assert not provider.is_function
    assert provider.is_class
    assert not provider.is_resource
    assert not provider.is_async_resource


def test_provider_function_resource() -> None:
    def resource() -> t.Iterator[str]:
        yield "test"

    provider = Provider(obj=resource, scope="transient")

    assert not provider.is_function
    assert not provider.is_class
    assert provider.is_resource
    assert not provider.is_async_resource


def test_provider_function_async_resource() -> None:
    async def resource() -> t.AsyncIterator[str]:
        yield "test"

    provider = Provider(obj=resource, scope="transient")

    assert not provider.is_function
    assert not provider.is_class
    assert not provider.is_resource
    assert provider.is_async_resource


def test_provider_name() -> None:
    def obj() -> str:
        return "test"

    provider = Provider(obj=obj, scope="transient")

    assert (
        provider.name
        == str(provider)
        == "tests.test_core.test_provider_name.<locals>.obj"
    )


def test_di_constructor_properties() -> None:
    di = PyxDI(default_scope="singleton", auto_register=True)

    assert di.default_scope == "singleton"
    assert di.auto_register
    assert di.providers == {}


def test_has_provider(di: PyxDI) -> None:
    di.register_provider(str, lambda: "test")

    assert di.has_provider(str)


def test_has_no_provider(di: PyxDI) -> None:
    assert not di.has_provider(str)


def test_register_provider(di: PyxDI) -> None:
    def provider_obj() -> str:
        return "test"

    provider = di.register_provider(str, provider_obj, scope="transient")

    assert provider.obj == provider_obj
    assert provider.scope == "transient"


def test_register_provider_default_scope() -> None:
    di = PyxDI(default_scope="singleton")

    def provider_obj() -> str:
        return "test"

    provider = di.register_provider(str, provider_obj)

    assert provider.obj == provider_obj
    assert provider.scope == di.default_scope


def test_register_provider_already_registered(di: PyxDI) -> None:
    di.register_provider(str, lambda: "test")

    with pytest.raises(ProviderError) as exc_info:
        di.register_provider(str, lambda: "other")

    assert str(exc_info.value) == "The provider interface `str` already registered."


def test_register_provider_override(di: PyxDI) -> None:
    di.register_provider(str, lambda: "test")

    def overriden_provider_obj() -> str:
        return "test"

    provider = di.register_provider(str, overriden_provider_obj, override=True)

    assert provider.obj == overriden_provider_obj


def test_register_annotated_type(di: PyxDI) -> None:
    di.register_provider(named(str, "msg1"), lambda: "test1")
    di.register_provider(named(str, "msg2"), lambda: "test2")

    assert Annotated[str, "msg1"] in di.providers
    assert Annotated[str, "msg2"] in di.providers


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


def test_unregister_request_scoped_provider_within_context(di: PyxDI) -> None:
    assert str not in di.providers

    with di.request_context() as ctx:
        ctx.set(str, "test")
        di.unregister_provider(str)

    assert str not in di.providers


def test_unregister_not_registered_provider(di: PyxDI) -> None:
    with pytest.raises(ProviderError) as exc_info:
        di.unregister_provider(str)

    assert str(exc_info.value) == "The provider interface `str` not registered."


def test_singleton(di: PyxDI) -> None:
    instance = "test"

    provider = di.singleton(str, instance)

    assert provider.scope == "singleton"
    assert callable(provider.obj)
    assert provider.obj() == instance


def test_get_provider(di: PyxDI) -> None:
    provider = di.register_provider(str, lambda: "str")

    assert di.get_provider(str) == provider


def test_get_provider_not_registered(di: PyxDI) -> None:
    with pytest.raises(ProviderError) as exc_info:
        assert di.get_provider(str)

    assert str(exc_info.value) == (
        "The provider interface for `str` has not been registered. Please ensure that "
        "the provider interface is properly registered before attempting to use it."
    )


# Validators


def test_register_provider_invalid_scope(di: PyxDI) -> None:
    with pytest.raises(InvalidScopeError) as exc_info:
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

    with pytest.raises(ProviderError) as exc_info:
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

    with pytest.raises(ProviderError) as exc_info:
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
    with pytest.raises(ProviderError) as exc_info:
        di.register_provider(str, "Test")  # type: ignore[arg-type]

    assert str(exc_info.value) == (
        "The provider `Test` is invalid because it is not a callable object. Only "
        "callable providers are allowed. Please update the provider to a callable "
        "object before attempting to register it."
    )


def test_register_valid_class_provider(di: PyxDI) -> None:
    class Klass:
        pass

    provider = di.register_provider(str, Klass)

    assert provider.is_class


@pytest.mark.parametrize(
    "scope1, scope2, scope3, valid",
    [
        (None, None, None, True),
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
    def mixed(a: int, b: float) -> str:
        return f"{a} * {b} = {a * b}"

    def a() -> int:
        return 2

    def b(a: int) -> float:
        return a * 2.5

    try:
        di.register_provider(str, mixed, scope=scope1)
        di.register_provider(int, a, scope=scope3)
        di.register_provider(float, b, scope=scope2)
    except ScopeMismatchError:
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

    with pytest.raises(ScopeMismatchError) as exc_info:
        di.register_provider(str, provider_str, scope="singleton")

    assert str(exc_info.value) == (
        "The provider `tests.test_core.test_register_provider_match_scopes_error"
        ".<locals>.provider_str` with a singleton scope was attempted to be registered "
        "with the provider `tests.test_core.test_register_provider_match_scopes_error"
        ".<locals>.provider_int` with a `request` scope, which is not allowed. "
        "Please ensure that all providers are registered with matching scopes."
    )


#
def test_register_provider_without_annotation(di: PyxDI) -> None:
    def service_ident() -> str:
        return "10000"

    def service(ident) -> Service:  # type: ignore[no-untyped-def]
        return Service(ident=ident)

    di.register_provider(str, service_ident)

    with pytest.raises(AnnotationError) as exc_info:
        di.register_provider(Service, service)

    assert str(exc_info.value) == (
        "Missing provider "
        "`tests.test_core.test_register_provider_without_annotation.<locals>.service` "
        "dependency `ident` annotation."
    )


def test_register_events(di: PyxDI) -> None:
    events = []

    @di.provider
    def message() -> str:
        return "test"

    @di.provider
    def event_1(message: str) -> t.Iterator[None]:
        events.append(f"event_1: before {message}")
        yield
        events.append(f"event_1: after {message}")

    @di.provider
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

    @di.provider
    def message() -> str:
        return "test"

    @di.provider
    async def event_1(message: str) -> t.AsyncIterator[None]:
        events.append(f"event_1: before {message}")
        yield
        events.append(f"event_1: after {message}")

    @di.provider
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


def test_validate_unresolved_provider_dependencies(di: PyxDI) -> None:
    def service(ident: str) -> Service:
        return Service(ident=ident)

    di.register_provider(Service, service)

    with pytest.raises(UnknownDependencyError) as exc_info:
        di.validate()

    assert str(exc_info.value) == (
        "The following unknown provided dependencies were detected:\n"
        "- `tests.test_core.test_validate_unresolved_provider_dependencies"
        ".<locals>.service` has unknown `ident: str` parameter."
    )


def test_validate_unresolved_injected_dependencies(di: PyxDI) -> None:
    def func1(service: Service = dep) -> None:
        return None

    def func2(message: str = dep) -> None:
        return None

    di.inject(func1)
    di.inject(func2)

    with pytest.raises(UnknownDependencyError) as exc_info:
        di.validate()

    assert str(exc_info.value) == (
        "The following unknown injected dependencies were detected:\n"
        "- `tests.test_core.test_validate_unresolved_injected_dependencies.<locals>"
        ".func1` has unknown `service: tests.fixtures.Service` injected parameter\n"
        "- `tests.test_core.test_validate_unresolved_injected_dependencies.<locals>"
        ".func2` has unknown `message: str` injected parameter."
    )


def test_validate_unresolved_injected_dependencies_auto_register_class() -> None:
    def func1(service: Service = dep) -> None:
        return None

    di = PyxDI(auto_register=True)
    di.inject(func1)
    di.validate()


# Module


class TestModule(Module):
    def configure(self, di: PyxDI) -> None:
        di.singleton(named(str, "msg1"), "Message 1")

    @provider
    def provide_msg2(self) -> t.Annotated[str, "msg2"]:
        return "Message 2"


def test_register_modules() -> None:
    di = PyxDI(modules=[TestModule])

    assert di.has_provider(named(str, "msg1"))
    assert di.has_provider(named(str, "msg2"))


def test_register_module_class(di: PyxDI) -> None:
    di.register_module(TestModule)

    assert di.has_provider(named(str, "msg1"))
    assert di.has_provider(named(str, "msg2"))


def test_register_module_instance(di: PyxDI) -> None:
    di.register_module(TestModule())

    assert di.has_provider(named(str, "msg1"))
    assert di.has_provider(named(str, "msg2"))


def test_register_module_function(di: PyxDI) -> None:
    def configure(di: PyxDI) -> None:
        di.singleton(str, "Message")

    di.register_module(configure)

    assert di.has_provider(str)


class OrderedModule(Module):
    @provider
    def dep3(self) -> Annotated[str, "dep3"]:
        return "dep3"

    @provider
    def dep1(self) -> Annotated[str, "dep1"]:
        return "dep1"

    @provider
    def dep2(self) -> Annotated[str, "dep2"]:
        return "dep2"


def test_register_module_ordered_providers(di: PyxDI) -> None:
    di.register_module(OrderedModule)

    assert list(di.providers.keys()) == [
        Annotated[str, "dep3"],
        Annotated[str, "dep1"],
        Annotated[str, "dep2"],
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

    assert di.get(str) == "test"

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
        assert di.get(str) == "test"

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

    assert di.get(str) == "test"

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
        assert await di.aget(str) == "test"

    assert events == ["dep1:before", "dep1:after"]


# Instance


def test_get_singleton_scoped(di: PyxDI) -> None:
    instance = "test"

    di.register_provider(str, lambda: instance, scope="singleton")

    assert di.get(str) == instance


def test_get_singleton_scoped_not_started(di: PyxDI) -> None:
    @di.provider
    def message() -> t.Iterator[str]:
        yield "test"

    assert di.get(str) == "test"


def test_get_singleton_scoped_resource(di: PyxDI) -> None:
    instance = "test"

    def provide() -> t.Iterator[str]:
        yield instance

    di.register_provider(str, provide, scope="singleton")
    di.start()

    assert di.get(str) == instance


def test_get_singleton_scoped_started_with_async_resource_provider(di: PyxDI) -> None:
    instance = "test"

    async def provide() -> t.AsyncIterator[str]:
        yield instance

    di.register_provider(str, provide, scope="singleton")

    with pytest.raises(ProviderError) as exc_info:
        di.start()

    assert str(exc_info.value) == (
        "The provider `tests.test_core.test_get_singleton_scoped_started_with_"
        "async_resource_provider.<locals>.provide` cannot be started in synchronous "
        "mode because it is an asynchronous provider. Please start the provider "
        "in asynchronous mode before using it."
    )


async def test_get_singleton_scoped_async_resource(di: PyxDI) -> None:
    instance = "test"

    def provide() -> t.Iterator[str]:
        yield instance

    di.register_provider(str, provide, scope="singleton")

    await di.astart()

    assert di.get(str) == instance


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

    assert di.get(str) == instance_str
    assert di.get(int) == instance_int


async def test_get_singleton_scoped_async_resource_not_started(di: PyxDI) -> None:
    instance = "test"

    async def provide() -> t.AsyncIterator[str]:
        yield instance

    di.register_provider(str, provide, scope="singleton")

    with pytest.raises(ProviderError) as exc_info:
        di.get(str)

    assert str(exc_info.value) == (
        "The instance for the resource provider "
        "`tests.test_core.test_get_singleton_scoped_async_resource_not_started"
        ".<locals>.provide` cannot be created until the scope context has been "
        "started. Please ensure that the scope context is started."
    )


def test_get_request_scoped(di: PyxDI) -> None:
    instance = "test"

    di.register_provider(str, lambda: instance, scope="request")

    with di.request_context():
        assert di.get(str) == instance


def test_get_request_scoped_not_started(di: PyxDI) -> None:
    instance = "test"

    di.register_provider(str, lambda: instance, scope="request")

    with pytest.raises(LookupError) as exc_info:
        assert di.get(str)

    assert str(exc_info.value) == (
        "The request context has not been started. Please ensure that the request "
        "context is properly initialized before attempting to use it."
    )


def test_get_transient_scoped(di: PyxDI) -> None:
    di.register_provider(uuid.UUID, uuid.uuid4, scope="transient")

    assert di.get(uuid.UUID) != di.get(uuid.UUID)


def test_get_async_transient_scoped(di: PyxDI) -> None:
    @di.provider(scope="transient")
    async def get_uuid() -> uuid.UUID:
        return uuid.uuid4()

    with pytest.raises(ProviderError) as exc_info:
        di.get(uuid.UUID)

    assert str(exc_info.value) == (
        "The instance for the coroutine provider "
        "`tests.test_core.test_get_async_transient_scoped.<locals>.get_uuid` "
        "cannot be created in synchronous mode."
    )


async def test_async_get_transient_scoped(di: PyxDI) -> None:
    @di.provider(scope="transient")
    async def get_uuid() -> uuid.UUID:
        return uuid.uuid4()

    assert await di.aget(uuid.UUID) != await di.aget(uuid.UUID)


async def test_async_get_synchronous_resource(di: PyxDI) -> None:
    @di.provider
    def msg() -> t.Iterator[str]:
        yield "test"

    assert await di.aget(str) == "test"


def test_get_auto_registered_instance() -> None:
    di = PyxDI(auto_register=True)

    class Service:
        __scope__ = "singleton"

    assert di.get(Service).__scope__ == "singleton"


def test_get_not_registered_instance(di: PyxDI) -> None:
    with pytest.raises(Exception) as exc_info:
        di.get(str)

    assert str(exc_info.value) == (
        "The provider interface for `str` has not been registered. Please ensure that "
        "the provider interface is properly registered before attempting to use it."
    )


def test_get_auto_registered_with_primitive_class() -> None:
    di = PyxDI(auto_register=True)

    @dataclass
    class Service:
        name: str

    with pytest.raises(ProviderError) as exc_info:
        _ = f"{di.get(Service).name}"

    assert str(exc_info.value) == (
        "The provider interface for `str` has not been registered. Please ensure that "
        "the provider interface is properly registered before attempting to use it."
    )


def test_has_instance(di: PyxDI) -> None:
    di.register_provider(str, lambda: "test")
    di.get(str)

    assert di.has(str)


def test_has_no_instance(di: PyxDI) -> None:
    di.register_provider(str, lambda: "test")

    assert not di.has(str)


def test_has_no_instance_and_provider(di: PyxDI) -> None:
    assert not di.has(str)


def test_has_instance_for_transient_provider(di: PyxDI) -> None:
    di.register_provider(str, lambda: "test", scope="transient")

    assert di.has(str)


def test_override(di: PyxDI) -> None:
    origin_name = "origin"
    overriden_name = "overriden"

    @di.provider
    def name() -> str:
        return origin_name

    with di.override(str, overriden_name):
        assert di.get(str) == overriden_name

    assert di.get(str) == origin_name


def test_override_auto_registered() -> None:
    di = PyxDI(auto_register=True)

    origin_name = "test"
    overriden_name = "overriden"

    @di.provider
    def name() -> str:
        return origin_name

    class Service:
        def __init__(self, name: str) -> None:
            self.name = name

    with di.override(Service, Service(name=overriden_name)):
        assert di.get(Service).name == overriden_name

    assert di.get(Service).name == origin_name


def test_override_transient_provider(di: PyxDI) -> None:
    overriden_uuid = uuid.uuid4()

    @di.provider(scope="transient")
    def uuid_provider() -> uuid.UUID:
        return uuid.uuid4()

    with di.override(uuid.UUID, overriden_uuid):
        assert di.get(uuid.UUID) == overriden_uuid

    assert di.get(uuid.UUID) != overriden_uuid


def test_override_resource_provider(di: PyxDI) -> None:
    origin = "origin"
    overriden = "overriden"

    @di.provider
    def message() -> t.Iterator[str]:
        yield origin

    with di.override(str, overriden):
        assert di.get(str) == overriden

    assert di.get(str) == origin


async def test_override_async_resource_provider(di: PyxDI) -> None:
    origin = "origin"
    overriden = "overriden"

    @di.provider
    async def message() -> t.AsyncIterator[str]:
        yield origin

    with di.override(str, overriden):
        assert di.get(str) == overriden

    # assert di.get(str) == origin


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

    with pytest.raises(AnnotationError) as exc_info:
        di._get_provider_annotation(provider)

    assert str(exc_info.value) == (
        "Missing `tests.test_core.test_get_provider_annotation_missing.<locals>"
        ".provider` provider return annotation."
    )


def test_get_provider_annotation_origin_without_args(di: PyxDI) -> None:
    def provider() -> list:  # type: ignore[type-arg]
        return []

    with pytest.raises(AnnotationError) as exc_info:
        di._get_provider_annotation(provider)

    assert str(exc_info.value) == (
        "Cannot use `tests.test_core.test_get_provider_annotation_origin_without_args."
        "<locals>.provider` generic type annotation without actual type."
    )


def test_get_provider_arguments(di: PyxDI) -> None:
    @di.provider
    def a() -> int:
        return 10

    @di.provider
    def b() -> float:
        return 1.0

    @di.provider
    def c() -> str:
        return "test"

    def service(a: int, /, b: float, *, c: str) -> Service:
        return Service(ident=f"{a}/{b}/{c}")

    provider = di.register_provider(Service, service)

    args, kwargs = di._get_provider_arguments(provider)

    assert args == [10]
    assert kwargs == {"b": 1.0, "c": "test"}


async def test_async_get_provider_arguments(di: PyxDI) -> None:
    @di.provider
    async def a() -> int:
        return 10

    @di.provider
    async def b() -> float:
        return 1.0

    @di.provider
    async def c() -> str:
        return "test"

    async def service(a: int, /, b: float, *, c: str) -> Service:
        return Service(ident=f"{a}/{b}/{c}")

    provider = di.register_provider(Service, service)

    args, kwargs = await di._aget_provider_arguments(provider)

    assert args == [10]
    assert kwargs == {"b": 1.0, "c": "test"}


def test_inject_missing_annotation(di: PyxDI) -> None:
    def func(name=dep) -> str:  # type: ignore[no-untyped-def]
        return name  # type: ignore[no-any-return]

    with pytest.raises(AnnotationError) as exc_info:
        di.inject(func)

    assert str(exc_info.value) == (
        "Missing `tests.test_core.test_inject_missing_annotation.<locals>.func` "
        "parameter annotation."
    )


def test_inject(di: PyxDI) -> None:
    @di.provider
    def ident_provider() -> str:
        return "1000"

    @di.provider
    def service_provider(ident: str) -> Service:
        return Service(ident=ident)

    @di.inject
    def func(name: str, service: Service = dep) -> str:
        return f"{name} = {service.ident}"

    result = func(name="service ident")

    assert result == "service ident = 1000"


def test_inject_class(di: PyxDI) -> None:
    @di.provider
    def ident_provider() -> str:
        return "1000"

    @di.provider
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
    @di.provider
    def ident_provider() -> str:
        return "1000"

    @di.provider
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

    di.register_provider(str, ident_provider)
    di.register_provider(Service, service_provider)

    await di.astart()

    @di.inject
    async def func(name: str, service: Service = dep) -> str:
        return f"{name} = {service.ident}"

    result = await func(name="service ident")

    assert result == "service ident = 1000"


def test_provider_decorator_no_args(di: PyxDI) -> None:
    @di.provider
    def ident() -> str:
        return "1000"

    assert di.get_provider(str) == Provider(obj=ident, scope=di.default_scope)


def test_provider_decorator_no_args_provided(di: PyxDI) -> None:
    @di.provider()
    def ident() -> str:
        return "1000"

    assert di.get_provider(str) == Provider(obj=ident, scope=di.default_scope)


def test_provider_decorator_with_provided_args(di: PyxDI) -> None:
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
