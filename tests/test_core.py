import typing as t
import uuid

import pytest

from pyxdi.core import DependencyParam, Provider, PyxDI
from pyxdi.exceptions import (
    AnnotationError,
    InvalidScope,
    ProviderError,
    ScopeMismatch,
    UnknownDependency,
)
from pyxdi.types import Scope

from tests.fixtures import Service


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


def test_have_not_provider(di: PyxDI) -> None:
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

    assert str(exc_info.value) == "Provider interface `str` already registered."


def test_register_provider_override(di: PyxDI) -> None:
    di.register_provider(str, lambda: "test")

    def overriden_provider_obj() -> str:
        return "test"

    provider = di.register_provider(str, overriden_provider_obj, override=True)

    assert provider.obj == overriden_provider_obj


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
    with pytest.raises(InvalidScope) as exc_info:
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
    except ScopeMismatch:
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

    with pytest.raises(ScopeMismatch) as exc_info:
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


def test_validate_unresolved_provider_dependencies(di: PyxDI) -> None:
    def service(ident: str) -> Service:
        return Service(ident=ident)

    di.register_provider(Service, service)

    with pytest.raises(UnknownDependency) as exc_info:
        di.validate()

    assert str(exc_info.value) == (
        "The following unknown provided dependencies were detected:\n"
        "- `tests.test_core.test_validate_unresolved_provider_dependencies"
        ".<locals>.service` has unknown `ident: str` parameter."
    )


def test_validate_unresolved_injected_dependencies(di: PyxDI) -> None:
    def func1(service: Service = DependencyParam()) -> None:
        return None

    def func2(message: str = DependencyParam()) -> None:
        return None

    di.inject(func1)
    di.inject(func2)

    with pytest.raises(UnknownDependency) as exc_info:
        di.validate()

    assert str(exc_info.value) == (
        "The following unknown injected dependencies were detected:\n"
        "- `tests.test_core.test_validate_unresolved_injected_dependencies.<locals>"
        ".func1` has unknown `service: tests.fixtures.Service` injected parameter\n"
        "- `tests.test_core.test_validate_unresolved_injected_dependencies.<locals>"
        ".func2` has unknown `message: str` injected parameter."
    )


def test_validate_unresolved_injected_dependencies_auto_register_class() -> None:
    def func1(service: Service = DependencyParam()) -> None:
        return None

    di = PyxDI(auto_register=True)
    di.inject(func1)
    di.validate()


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


@pytest.mark.anyio
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


@pytest.mark.anyio
async def test_arequest_context(di: PyxDI) -> None:
    events = []

    async def dep1() -> t.AsyncIterator[str]:
        events.append("dep1:before")
        yield "test"
        events.append("dep1:after")

    di.register_provider(str, dep1, scope="request")

    async with await di.arequest_context():
        assert di.get(str) == "test"

    assert events == ["dep1:before", "dep1:after"]


# Instance


def test_get_singleton_scoped(di: PyxDI) -> None:
    instance = "test"

    di.register_provider(str, lambda: instance, scope="singleton")

    assert di.get(str) == instance


def test_get_singleton_scoped_not_started(di: PyxDI) -> None:
    def provider() -> t.Iterator[str]:
        yield "test"

    di.register_provider(str, provider, scope="singleton")

    with pytest.raises(ProviderError) as exc_info:
        di.get(str)

    assert str(exc_info.value) == (
        "The instance for the resource provider `tests.test_core.test_get_singleton_"
        "scoped_not_started.<locals>.provider` cannot be created until the scope "
        "context has been started. Please ensure that the scope context is started."
    )


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


@pytest.mark.anyio
async def test_get_singleton_scoped_async_resource(di: PyxDI) -> None:
    instance = "test"

    def provide() -> t.Iterator[str]:
        yield instance

    di.register_provider(str, provide, scope="singleton")

    await di.astart()

    assert di.get(str) == instance


@pytest.mark.anyio
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


def test_get_injectable_params_missing_annotation(di: PyxDI) -> None:
    def func(name=DependencyParam()) -> str:  # type: ignore[no-untyped-def]
        return name  # type: ignore[no-any-return]

    with pytest.raises(AnnotationError) as exc_info:
        di.inject(func)

    assert str(exc_info.value) == (
        "Missing `tests.test_core.test_get_injectable_params_missing_annotation"
        ".<locals>.func` parameter annotation."
    )


def test_get_injectable_params(di: PyxDI) -> None:
    @di.provider
    def ident() -> str:
        return "1000"

    @di.provider
    def service(ident: str) -> Service:
        return Service(ident=ident)

    @di.inject
    def func(name: str, service: Service = DependencyParam()) -> str:
        return f"{name} = {service.ident}"

    result = func(name="service ident")

    assert result == "service ident = 1000"


def test_get_provider_arguments(di: PyxDI) -> None:
    def a() -> int:
        return 10

    def b() -> float:
        return 1.0

    def c() -> str:
        return "test"

    def service(a: int, /, b: float, *, c: str) -> Service:
        return Service(ident=f"{a}/{b}/{c}")

    di.register_provider(int, a)
    di.register_provider(float, b)
    di.register_provider(str, c)
    provider = di.register_provider(Service, service)

    args, kwargs = di._get_provider_arguments(provider)

    assert args == [10]
    assert kwargs == {"b": 1.0, "c": "test"}
