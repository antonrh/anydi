from abc import ABC, abstractmethod

import pytest

from anydi import Module, injectable, provided, provider, request, singleton, transient
from anydi._decorators import is_injectable, is_provided


class IService(ABC):
    @abstractmethod
    def do_something(self) -> None:
        pass


# provided decorator tests


def test_provided_decorator() -> None:
    @provided(scope="singleton")
    class Service:
        pass

    assert is_provided(Service)
    assert Service.__provided__ == {
        "scope": "singleton",
        "from_context": False,
    }


def test_provided_decorator_with_dependency_type() -> None:
    @provided(IService, scope="singleton")
    class ServiceImpl:
        def do_something(self) -> None:
            pass

    assert is_provided(ServiceImpl)
    assert ServiceImpl.__provided__ == {
        "dependency_type": IService,
        "scope": "singleton",
        "from_context": False,
    }


# singleton decorator tests


def test_singleton_decorator() -> None:
    @singleton
    class Service:
        pass

    assert is_provided(Service)
    assert Service.__provided__ == {
        "scope": "singleton",
        "from_context": False,
    }


def test_singleton_decorator_call() -> None:
    @singleton()
    class Service:
        pass

    assert is_provided(Service)
    assert Service.__provided__ == {
        "scope": "singleton",
        "from_context": False,
    }


def test_singleton_decorator_with_dependency_type() -> None:
    @singleton(dependency_type=IService)
    class ServiceImpl:
        def do_something(self) -> None:
            pass

    assert is_provided(ServiceImpl)
    assert ServiceImpl.__provided__ == {
        "dependency_type": IService,
        "scope": "singleton",
        "from_context": False,
    }


# transient decorator tests


def test_transient_decorator() -> None:
    @transient
    class Service:
        pass

    assert is_provided(Service)
    assert Service.__provided__ == {
        "scope": "transient",
        "from_context": False,
    }


def test_transient_decorator_call() -> None:
    @transient()
    class Service:
        pass

    assert is_provided(Service)
    assert Service.__provided__ == {
        "scope": "transient",
        "from_context": False,
    }


def test_transient_decorator_with_dependency_type() -> None:
    @transient(dependency_type=IService)
    class ServiceImpl:
        def do_something(self) -> None:
            pass

    assert is_provided(ServiceImpl)
    assert ServiceImpl.__provided__ == {
        "dependency_type": IService,
        "scope": "transient",
        "from_context": False,
    }


def test_transient_decorator_invalid_args() -> None:
    with pytest.raises(TypeError):
        transient(from_context=True)  # type: ignore


# request decorator tests


def test_request_decorator() -> None:
    @request
    class Service:
        pass

    assert is_provided(Service)
    assert Service.__provided__ == {
        "scope": "request",
        "from_context": False,
    }


def test_request_decorator_call() -> None:
    @request()
    class Service:
        pass

    assert is_provided(Service)
    assert Service.__provided__ == {
        "scope": "request",
        "from_context": False,
    }


def test_request_decorator_with_from_context() -> None:
    @request(from_context=True)
    class Service:
        pass

    assert is_provided(Service)
    assert Service.__provided__ == {
        "scope": "request",
        "from_context": True,
    }


def test_request_decorator_with_dependency_type() -> None:
    @request(dependency_type=IService)
    class ServiceImpl:
        def do_something(self) -> None:
            pass

    assert is_provided(ServiceImpl)
    assert ServiceImpl.__provided__ == {
        "dependency_type": IService,
        "scope": "request",
        "from_context": False,
    }


def test_request_decorator_with_dependency_type_and_from_context() -> None:
    @request(dependency_type=IService, from_context=True)
    class ServiceImpl:
        def do_something(self) -> None:
            pass

    assert is_provided(ServiceImpl)
    assert ServiceImpl.__provided__ == {
        "dependency_type": IService,
        "scope": "request",
        "from_context": True,
    }


# provider decorator tests


def test_provider_decorator() -> None:
    class TestModule(Module):
        @provider(scope="singleton", override=True)
        def provide_str(self) -> str:
            return "test"

    assert getattr(TestModule.provide_str, "__provider__") == {
        "scope": "singleton",
        "override": True,
    }


# injectable decorator tests


def test_injectable_decorator() -> None:
    @injectable
    def my_func() -> None:
        pass

    assert is_injectable(my_func)
    assert my_func.__injectable__ == {
        "tags": None,
    }


def test_injectable_decorator_call() -> None:
    @injectable()
    def my_func() -> None:
        pass

    assert is_injectable(my_func)
    assert my_func.__injectable__ == {
        "tags": None,
    }


def test_injectable_decorator_with_tags() -> None:
    @injectable(tags=["tag1", "tag2"])
    def my_func() -> None:
        pass

    assert is_injectable(my_func)
    assert my_func.__injectable__ == {
        "tags": ["tag1", "tag2"],
    }
