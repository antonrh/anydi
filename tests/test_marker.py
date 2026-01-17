import pytest

from anydi._marker import Marker


class TestMarker:
    def test_dependency_type_not_set(self) -> None:
        marker = Marker()

        with pytest.raises(TypeError, match="Dependency type is not set"):
            _ = marker.dependency_type

    def test_attr_fallback_lookup(self) -> None:
        marker = Marker()

        # Set preferred owner
        marker.set_owner("framework1")

        # Set an attribute with framework1 as owner
        marker._current_owner = "framework1"
        marker.dependency = "value1"

        # Set another attribute with framework2 as owner
        marker._current_owner = "framework2"
        marker.use_cache = True

        # Now set preferred owner to framework2
        marker.set_owner("framework2")

        # Should find use_cache in framework2
        assert marker.use_cache is True

        # Should fall back to framework1 for dependency
        assert marker.dependency == "value1"

    def test_attr_not_found(self) -> None:
        marker = Marker()

        with pytest.raises(AttributeError):
            _ = marker.dependency
