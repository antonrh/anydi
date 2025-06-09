from anydi import Module, injectable, provider, request, singleton, transient

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

    assert getattr(Service, "__scope__") == "request"


def test_transient_decorator() -> None:
    transient(Service)

    assert getattr(Service, "__scope__") == "transient"


def test_singleton_decorator() -> None:
    singleton(Service)

    assert getattr(Service, "__scope__") == "singleton"


def test_injectable_no_args() -> None:
    @injectable
    def my_func() -> None:
        pass

    assert getattr(my_func, "__injectable__") == {
        "wrapped": True,
        "tags": None,
    }


def test_injectable_no_args_provided() -> None:
    @injectable()
    def my_func() -> None:
        pass

    assert getattr(my_func, "__injectable__") == {"wrapped": True, "tags": None}


def test_injectable_with_tags() -> None:
    @injectable(tags=["tag1", "tag2"])
    def my_func() -> None:
        pass

    assert getattr(my_func, "__injectable__") == {
        "wrapped": True,
        "tags": ["tag1", "tag2"],
    }
