from pyxdi.core import Module
from pyxdi.decorators import inject, provider


def test_provider_no_args() -> None:
    class TestModule(Module):
        @provider
        def provider(self) -> str:
            return "test"

    assert getattr(TestModule.provider, "__pyxdi_provider__") == {
        "scope": None,
        "override": None,
    }


def test_provider_no_args_provided() -> None:
    class TestModule(Module):
        @provider()
        def provider(self) -> str:
            return "test"

    assert getattr(TestModule.provider, "__pyxdi_provider__") == {
        "scope": None,
        "override": None,
    }


def test_provider() -> None:
    class TestModule(Module):
        @provider(scope="singleton", override=True)
        def provider(self) -> str:
            return "test"

    assert getattr(TestModule.provider, "__pyxdi_provider__") == {
        "scope": "singleton",
        "override": True,
    }


def test_inject_no_args() -> None:
    @inject
    def my_func() -> None:
        pass

    assert getattr(my_func, "__pyxdi_inject__") is True
    assert getattr(my_func, "__pyxdi_tags__") is None


def test_inject_no_args_provided() -> None:
    @inject()
    def my_func() -> None:
        pass

    assert getattr(my_func, "__pyxdi_inject__") is True
    assert getattr(my_func, "__pyxdi_tags__") is None


def test_inject() -> None:
    @inject(tags=["tag1", "tag2"])
    def my_func() -> None:
        pass

    assert getattr(my_func, "__pyxdi_inject__") is True
    assert getattr(my_func, "__pyxdi_tags__") == ["tag1", "tag2"]
