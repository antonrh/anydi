from anydi import Module, injectable, provider, request, singleton, transient
from anydi._decorators import is_injectable, is_provided

from tests.fixtures import Service


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
    request(Service)

    assert is_provided(Service)
    assert Service.__provided__ == {
        "scope": "request",
    }


def test_transient_decorator() -> None:
    transient(Service)

    assert is_provided(Service)
    assert Service.__provided__ == {
        "scope": "transient",
    }


def test_singleton_decorator() -> None:
    singleton(Service)

    assert is_provided(Service)
    assert Service.__provided__ == {
        "scope": "singleton",
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
