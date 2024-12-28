import abc
import sys
import uuid
from collections.abc import AsyncIterator, Iterator, Sequence
from dataclasses import dataclass
from typing import Annotated, Any, Union
from unittest import mock

import pytest
from typing_extensions import Self

from anydi import Container, Provider, Scope, auto, request, singleton, transient

from tests.fixtures import Resource, Service


@pytest.fixture
def container() -> Container:
    return Container()


def test_default_strict_disabled(container: Container) -> None:
    assert not container.strict


def test_register_provider(container: Container) -> None:
    def provider_call() -> str:
        return "test"

    provider = container.register(str, provider_call, scope="transient")

    assert provider.call == provider_call
    assert provider.scope == "transient"


def test_register_provider_already_registered(container: Container) -> None:
    container.register(str, lambda: "test", scope="singleton")

    with pytest.raises(LookupError) as exc_info:
        container.register(str, lambda: "other", scope="singleton")

    assert str(exc_info.value) == "The provider interface `str` already registered."


def test_register_provider_override(container: Container) -> None:
    container.register(str, lambda: "old", scope="singleton")

    def new_provider_call() -> str:
        return "new"

    provider = container.register(
        str, new_provider_call, scope="singleton", override=True
    )

    assert provider.call == new_provider_call


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
        providers=[
            Provider(call=lambda: "test", scope="singleton", interface=str),
            Provider(call=lambda: 1, scope="singleton", interface=int),
        ]
    )

    assert container.is_registered(str)
    assert container.is_registered(int)


def test_register_provider_invalid_transient_resource(container: Container) -> None:
    def provider_call() -> Iterator[str]:
        yield "test"

    with pytest.raises(TypeError) as exc_info:
        container.register(str, provider_call, scope="transient")

    assert str(exc_info.value) == (
        "The resource provider `tests.test_container"
        ".test_register_provider_invalid_transient_resource.<locals>.provider_call` is "
        "attempting to register with a transient scope, which is not allowed."
    )


def test_register_provider_invalid_transient_async_resource(
    container: Container,
) -> None:
    async def provider_call() -> AsyncIterator[str]:
        yield "test"

    with pytest.raises(TypeError) as exc_info:
        container.register(str, provider_call, scope="transient")

    assert str(exc_info.value) == (
        "The resource provider `tests.test_container"
        ".test_register_provider_invalid_transient_async_resource"
        ".<locals>.provider_call` is attempting to register with a transient scope, "
        "which is not allowed."
    )


def test_register_provider_valid_resource(container: Container) -> None:
    def provider_call1() -> Iterator[str]:
        yield "test"

    def provider_call2() -> Iterator[int]:
        yield 100

    container.register(str, provider_call1, scope="singleton")
    container.register(int, provider_call2, scope="request")


def test_register_provider_valid_async_resource(container: Container) -> None:
    async def provider_call1() -> AsyncIterator[str]:
        yield "test"

    async def provider_call2() -> AsyncIterator[int]:
        yield 100

    container.register(str, provider_call1, scope="singleton")
    container.register(int, provider_call2, scope="request")


def test_register_invalid_provider_type(container: Container) -> None:
    with pytest.raises(TypeError) as exc_info:
        container.register(str, "Test", scope="singleton")  # type: ignore[arg-type]

    assert str(exc_info.value) == (
        "The provider `Test` is invalid because it is not a callable object. Only "
        "callable providers are allowed."
    )


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
        "The provider `tests.test_container.test_register_provider_match_scopes_error."
        "<locals>.provider_str` with a `singleton` scope cannot depend on "
        "`tests.test_container.test_register_provider_match_scopes_error.<locals>."
        "provider_int` with a `request` scope. Please ensure all providers are "
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
        "registered or set. To resolve this, ensure that `dep1` is registered "
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


def test_resolve_singleton_annotated_resource(container: Container) -> None:
    instance = "test"

    @container.provider(scope="singleton")
    def provide() -> Iterator[Annotated[str, "message"]]:
        yield instance

    result = container.resolve(Annotated[str, "message"])

    assert result == instance


async def test_resolve_singleton_annotated_async_resource(container: Container) -> None:
    instance = "test"

    @container.provider(scope="singleton")
    async def provide() -> AsyncIterator[Annotated[str, "message"]]:
        yield instance

    result = await container.aresolve(Annotated[str, "message"])

    assert result == instance


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


def test_resolve_request_scoped_annotated_resource(container: Container) -> None:
    instance = "test"

    @container.provider(scope="request")
    def provide() -> Iterator[Annotated[str, "message"]]:
        yield instance

    with container.request_context():
        result = container.resolve(Annotated[str, "message"])

    assert result == instance


async def test_resolve_request_scoped_annotated_async_resource(
    container: Container,
) -> None:
    instance = "test"

    @container.provider(scope="request")
    async def provide() -> AsyncIterator[Annotated[str, "message"]]:
        yield instance

    async with container.arequest_context():
        result = await container.aresolve(Annotated[str, "message"])

    assert result == instance


def test_resolve_request_scoped_unresolved_yet(container: Container) -> None:
    class Request:
        def __init__(self, path: str) -> None:
            self.path = path

    @container.provider(scope="request")
    def req_path(req: Request) -> str:
        return req.path

    with container.request_context() as ctx:
        ctx.set(Request, Request(path="test"))
        assert container.resolve(str) == "test"


def test_resolve_request_scoped_unresolved_error(container: Container) -> None:
    class Request:
        def __init__(self, path: str) -> None:
            self.path = path

    @container.provider(scope="request")
    def req_path(req: Request) -> str:
        return req.path

    with container.request_context():
        with pytest.raises(LookupError) as exc_info:
            container.resolve(str)

    assert str(exc_info.value) == (
        "You are attempting to get the parameter `req` with the annotation "
        "`tests.test_container.test_resolve_request_scoped_unresolved_error.<locals>"
        ".Request` as a dependency into `tests.test_container"
        ".test_resolve_request_scoped_unresolved_error.<locals>.req_path` which is not "
        "registered or set in the scoped context."
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

    assert container.providers == {Service: Provider(call=Service, scope="singleton")}


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
        str: Provider(call=message, scope="request"),
        Service: Provider(call=Service, scope="request"),
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


@pytest.mark.skipif(sys.version_info < (3, 10), reason="Requires Python 3.10")
def test_resolve_non_strict_with_custom_type(container: Container) -> None:
    class Klass:
        def __init__(self, value: "Union[str, Sequence[str], int, list[str]]") -> None:
            self.value = value

    with pytest.raises(LookupError) as exc_info:
        _ = container.resolve(Klass)

    assert str(exc_info.value) == (
        "The provider interface for "
        "`Union[str, Sequence[str], int, list[str]]` has not "
        "been registered. Please ensure that the provider interface is properly "
        "registered before attempting to use it."
    )


def test_resolve_non_strict_with_as_context_manager(container: Container) -> None:
    class Service:
        __scope__ = "singleton"

        def __init__(self) -> None:
            self.entered = False
            self.exited = False

        def __enter__(self) -> Self:
            self.entered = True
            return self

        def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
            self.exited = True

    service = container.resolve(Service)

    assert service.entered

    container.close()

    assert service.exited


async def test_resolve_non_strict_with_as_async_context_manager(
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
    overridden_name = "overridden"

    @container.provider(scope="singleton")
    def name() -> str:
        return origin_name

    with container.override(str, overridden_name):
        assert container.resolve(str) == overridden_name

    assert container.resolve(str) == origin_name


def test_override_instance_provider_not_registered_using_strict_mode() -> None:
    container = Container(strict=True)

    with pytest.raises(LookupError) as exc_info:
        with container.override(str, "test"):
            pass

    assert str(exc_info.value) == "The provider interface `str` not registered."


def test_override_instance_transient_provider(container: Container) -> None:
    overridden_uuid = uuid.uuid4()

    @container.provider(scope="transient")
    def uuid_provider() -> uuid.UUID:
        return uuid.uuid4()

    with container.override(uuid.UUID, overridden_uuid):
        assert container.resolve(uuid.UUID) == overridden_uuid

    assert container.resolve(uuid.UUID) != overridden_uuid


def test_override_instance_resource_provider(container: Container) -> None:
    origin = "origin"
    overridden = "overridden"

    @container.provider(scope="singleton")
    def message() -> Iterator[str]:
        yield origin

    with container.override(str, overridden):
        assert container.resolve(str) == overridden

    assert container.resolve(str) == origin


async def test_override_instance_async_resource_provider(container: Container) -> None:
    origin = "origin"
    overridden = "overridden"

    @container.provider(scope="singleton")
    async def message() -> AsyncIterator[str]:
        yield origin

    with container.override(str, overridden):
        assert container.resolve(str) == overridden


def test_override_instance_testing() -> None:
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


def test_resource_delegated_exception(container: Container) -> None:
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

    with pytest.raises(ValueError), container.request_context():
        resource = container.resolve(Resource)
        resource.run()
        raise ValueError

    assert resource.called
    assert not resource.committed
    assert resource.rolled_back


async def test_async_resource_delegated_exception(container: Container) -> None:
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

    with pytest.raises(ValueError):
        async with container.arequest_context():
            resource = await container.aresolve(Resource)
            resource.run()
            raise ValueError

    assert resource.called
    assert not resource.committed
    assert resource.rolled_back


def test_alias_string(container: Container) -> None:
    container.register(
        Annotated[str, "message"],
        lambda: "test",
        scope="singleton",
    )

    container.alias(Annotated[str, "message"], Annotated[str, "alias"])

    assert container.resolve(Annotated[str, "message"]) == container.resolve(
        Annotated[str, "alias"]
    )


def test_alias_already_registered(container: Container) -> None:
    container.register(
        Annotated[str, "message"],
        lambda: "test",
        scope="singleton",
    )

    container.alias(Annotated[str, "message"], Annotated[str, "alias"])

    with pytest.raises(LookupError) as exc_info:
        container.alias(Annotated[str, "message"], Annotated[str, "alias"])

    assert str(exc_info.value) == (
        "The interface `Annotated[str, str]` is already aliased."
    )


def test_alias_multiple_aliases(container: Container) -> None:
    container.register(
        Annotated[str, "message"],
        lambda: "test",
        scope="singleton",
    )

    container.alias(
        Annotated[str, "message"],
        Annotated[str, "alias1"] | Annotated[str, "alias2"] | Annotated[str, "alias3"],
    )

    assert (
        container.resolve(Annotated[str, "message"])
        == container.resolve(Annotated[str, "alias1"])
        == container.resolve(Annotated[str, "alias2"])
        == container.resolve(Annotated[str, "alias3"])
    )


def test_aliased_object(container: Container) -> None:
    class Greeting:
        def __init__(self, message: str) -> None:
            self.message = message

    class IGreeter(abc.ABC):
        @abc.abstractmethod
        def greet(self) -> Greeting:
            pass

    class GreeterService(IGreeter):
        def __init__(self, greeting: Greeting) -> None:
            self.greeting = greeting

        def greet(self) -> Greeting:
            return self.greeting

    container.register(
        GreeterService,
        lambda: GreeterService(Greeting("test")),
        scope="singleton",
    )

    container.alias(GreeterService, IGreeter)

    assert container.resolve(GreeterService) is container.resolve(IGreeter)


def test_alias_with_register(container: Container) -> None:
    container.register(
        Annotated[str, "message"] | Annotated[str, "alias1"] | Annotated[str, "alias2"],
        lambda: "test",
        scope="singleton",
    )

    assert (
        container.resolve(Annotated[str, "message"])
        == container.resolve(Annotated[str, "alias1"])
        == container.resolve(Annotated[str, "alias2"])
    )


# Inspections


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

    args, kwargs = scoped_context._get_provider_params(provider)

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

    args, kwargs = await scoped_context._aget_provider_params(provider)

    assert args == [10]
    assert kwargs == {"b": 1.0, "c": "test"}


def test_run(container: Container) -> None:
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


def test_provider_decorator(container: Container) -> None:
    @container.provider(scope="singleton")
    def ident() -> str:
        return "1000"

    assert container.providers[str] == Provider(call=ident, scope="singleton")


def test_request_decorator() -> None:
    request(Service)

    assert getattr(Service, "__scope__") == "request"


def test_transient_decorator() -> None:
    transient(Service)

    assert getattr(Service, "__scope__") == "transient"


def test_singleton_decorator() -> None:
    singleton(Service)

    assert getattr(Service, "__scope__") == "singleton"
