"""Testing utilities for AnyDI.

.. deprecated:: 0.56.0
    TestContainer is deprecated. Use Container with override() instead.
"""

from __future__ import annotations

import warnings

from ._container import Container


class TestContainer(Container):
    """Test container for dependency injection.

    .. deprecated:: 0.56.0
        TestContainer is deprecated and will be removed in a future version.
        Use regular Container with override() method instead.
    """

    __test__ = False

    def __init__(self, *args, **kwargs):  # type: ignore
        warnings.warn(
            "TestContainer is deprecated and will be removed in a future version. "
            "Use regular Container with override() method instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)

    @classmethod
    def from_container(cls, container: Container) -> Container:
        """Create a test container from an existing container.

        .. deprecated:: 0.56.0
            This method is deprecated. Just use the container directly.
        """
        warnings.warn(
            "TestContainer.from_container() is deprecated. "
            "Use the container directly with override() method.",
            DeprecationWarning,
            stacklevel=2,
        )
        return container
