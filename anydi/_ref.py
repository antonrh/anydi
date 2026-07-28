"""Lazy dependency reference module."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from typing_extensions import type_repr

# Pure-Python `ObjectProxy`: the C one ignores a `__wrapped__` property override
from wrapt.wrappers import ObjectProxy  # ty: ignore[unresolved-import]

from ._types import NOT_SET

if TYPE_CHECKING:
    from ._container import Container


class Ref(ObjectProxy):
    """A lazy reference to a dependency, resolved on first attribute access."""

    __slots__ = (
        "_self_cache",
        "_self_container",
        "_self_dependency_type",
        "_self_epoch",
        "_self_instance",
    )

    def __init__(
        self, container: Container | None, dependency_type: Any, *, cache: bool = True
    ) -> None:
        # `ObjectProxy.__init__` is skipped: it assigns to the `__wrapped__` property
        self._self_container: Any = container
        self._self_dependency_type = dependency_type
        self._self_cache = cache
        self._self_instance: Any = NOT_SET
        self._self_epoch = -1

    @property
    def __wrapped__(self) -> Any:
        container: Container = self._self_container
        epoch = container._epoch
        # The epoch is read before the instance, the reverse of the write order
        if self._self_epoch == epoch:
            return self._self_instance

        instance = container.resolve(self._self_dependency_type)

        # Only singletons are cached, otherwise instances would leak across scopes
        if self._self_cache:
            scope = container._get_provider(self._self_dependency_type).scope
            if scope == "singleton":
                self._self_instance = instance
                self._self_epoch = epoch
            else:
                self._self_cache = False

        return instance

    def __getattr__(self, name: str) -> Any:
        # Fast path for a cached instance, skipping the `__wrapped__` property
        if self._self_epoch == self._self_container._epoch:
            return getattr(self._self_instance, name)
        return getattr(self.__wrapped__, name)

    def __repr__(self) -> str:
        # Deliberately does not resolve the dependency
        return f"<{type(self).__name__} for {type_repr(self._self_dependency_type)}>"
