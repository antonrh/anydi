import pytest

from anydi import Module, injectable, provider, request, singleton, transient
from anydi._decorators import is_injectable, is_provided


def test_provider_decorator() -> None:
    class TestModule(Module):
        @provider(scope="singleton", override=True)
        def provider(self) -> str:
            return "test"

    assert getattr(TestModule.provider, "__provider__") == {
        "scope": "singleton",
        "override": True,
    }


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
    class ServiceEmptyArgs:
        pass

    assert is_provided(ServiceEmptyArgs)

    assert ServiceEmptyArgs.__provided__ == {
        "scope": "request",
        "from_context": False,
    }


def test_request_decorator_with_args() -> None:
    @request(from_context=True)
    class ServiceWithArgs:
        pass

    assert is_provided(ServiceWithArgs)

    assert ServiceWithArgs.__provided__ == {
        "scope": "request",
        "from_context": True,
    }


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
    class ServiceTransient:
        pass

    assert is_provided(ServiceTransient)

    assert ServiceTransient.__provided__ == {
        "scope": "transient",
        "from_context": False,
    }


def test_transient_decorator_invalid_args() -> None:
    with pytest.raises(TypeError):
        transient(from_context=True)  # type: ignore


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
    class ServiceSingleton:
        pass

    assert is_provided(ServiceSingleton)

    assert ServiceSingleton.__provided__ == {
        "scope": "singleton",
        "from_context": False,
    }


def test_injectable_no_args() -> None:
    @injectable
    def my_func() -> None:
        pass

    assert is_injectable(my_func)
    assert my_func.__injectable__ == {
        "tags": None,
    }


def test_injectable_no_args_provided() -> None:
    @injectable()
    def my_func() -> None:
        pass

    assert is_injectable(my_func)
    assert my_func.__injectable__ == {
        "tags": None,
    }


def test_injectable_with_tags() -> None:
    @injectable(tags=["tag1", "tag2"])
    def my_func() -> None:
        pass

    assert is_injectable(my_func)
    assert my_func.__injectable__ == {
        "tags": ["tag1", "tag2"],
    }
