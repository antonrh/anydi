from __future__ import annotations

from ._container import Container


class TestContainer(Container):
    __test__ = False

    @classmethod
    def from_container(cls, container: Container) -> Container:
        return container
