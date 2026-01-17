import pytest

from anydi import Provider


def test_provider_deprecated_interface():
    """Test Provider with deprecated interface argument."""
    with pytest.warns(
        DeprecationWarning,
        match="The `interface` is deprecated. Use `dependency_type` instead.",
    ):
        provider = Provider(interface=int)

    assert provider.dependency_type is int
    assert provider.interface is int


def test_provider_deprecated_call():
    """Test Provider with deprecated call argument."""

    def my_factory() -> str:
        return "hello"

    with pytest.warns(
        DeprecationWarning, match="The `call` is deprecated. Use `factory` instead."
    ):
        provider = Provider(str, call=my_factory)

    assert provider.factory is my_factory
    assert provider.call is my_factory


def test_provider_deprecated_both():
    """Test Provider with both deprecated interface and call arguments."""

    def my_factory() -> int:
        return 42

    with pytest.warns(DeprecationWarning, match="is deprecated"):
        provider = Provider(interface=int, call=my_factory)

    assert provider.dependency_type is int
    assert provider.factory is my_factory


def test_provider_post_init_sync():
    """Test that dependency_type and interface are synced after init."""
    provider = Provider(dependency_type=int)
    assert provider.interface is int

    provider.dependency_type = str
    provider.__post_init__()
    assert provider.interface is str


def test_provider_factory_sync():
    """Test that factory and call are synced after init."""

    def f1():
        pass

    def f2():
        pass

    provider = Provider(int, factory=f1)
    assert provider.call is f1

    provider.factory = f2
    provider.__post_init__()
    assert provider.call is f2
