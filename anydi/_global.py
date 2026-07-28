"""Global container access module."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any, TypeVar, cast

from typing_extensions import TypeForm, type_repr

from ._container import Container
from ._module import ModuleDef
from ._provider import ProviderDef
from ._ref import Ref
from ._types import NOT_SET

__all__ = [
    "GlobalRef",
    "create_global_container",
    "get_global_container",
    "get_global_container_or_none",
    "global_ref",
    "reset_global_container",
    "set_global_container",
    "uses_global_container",
]

T = TypeVar("T", bound=Any)


_container: Container | None = None
_refs: list[GlobalRef] = []


def create_global_container(
    *,
    providers: Iterable[ProviderDef] | None = None,
    modules: Iterable[ModuleDef] | None = None,
    logger: logging.Logger | None = None,
) -> Container:
    """Create a container and make it the global one."""
    container = Container(providers=providers, modules=modules, logger=logger)
    set_global_container(container)
    return container


def set_global_container(container: Container) -> None:
    """Make the container globally available to references."""
    global _container

    if _container is not None and _container is not container:
        raise RuntimeError(
            "The global container is already set. Call "
            "`reset_global_container()` first if you intend to replace it."
        )

    _container = container

    for global_ref in _refs:
        global_ref._unbind()
        # Let build() report a reference the container cannot resolve
        dependency_type = global_ref._self_dependency_type
        if dependency_type not in container._pending_refs:
            container._pending_refs.append(dependency_type)


def get_global_container() -> Container:
    """Get the global container."""
    if _container is None:
        raise RuntimeError(
            "The global container is not set. Create it with "
            "`create_global_container()` or register an existing one with "
            "`set_global_container()`."
        )
    return _container


def get_global_container_or_none() -> Container | None:
    """Get the global container, or None when it is not set."""
    return _container


def uses_global_container() -> bool:
    """Check whether the global container is set or referenced."""
    return _container is not None or bool(_refs)


def reset_global_container() -> None:
    """Unset the global container, leaving references unbound."""
    global _container

    _container = None

    for global_ref in _refs:
        global_ref._unbind()


class GlobalRef(Ref):
    """A lazy reference resolved against the global container."""

    __slots__ = ()

    def __init__(self, dependency_type: Any, *, cache: bool = True) -> None:
        # The reference stays unbound until used, so a module holding it can be
        # imported in any order relative to the container
        super().__init__(None, dependency_type, cache=cache)
        _refs.append(self)

    def _unbind(self) -> None:
        """Detach the reference, so the next access binds it again."""
        self._self_container = None
        self._self_instance = NOT_SET
        self._self_epoch = -1

    def _bind(self) -> None:
        """Attach the reference to the global container and validate it."""
        container = _container
        if container is None:
            raise RuntimeError(
                f"Cannot resolve `{type_repr(self._self_dependency_type)}`: the "
                "global container is not set. Create it with "
                "`create_global_container()` or register an existing one with "
                "`set_global_container()`."
            )
        container._validate_ref(self._self_dependency_type)
        self._self_container = container

    def __repr__(self) -> str:
        if self._self_container is not None:
            return super().__repr__()
        dependency_repr = type_repr(self._self_dependency_type)
        return f"<{type(self).__name__} for {dependency_repr}, unbound>"

    @property
    def __wrapped__(self) -> Any:
        if self._self_container is None:
            self._bind()
        return super().__wrapped__

    def __getattr__(self, name: str) -> Any:
        # The fast path of `Ref` is inlined here to keep access to one call
        container = self._self_container
        if container is None:
            self._bind()
        elif self._self_epoch == container._epoch:
            return getattr(self._self_instance, name)
        return getattr(self.__wrapped__, name)


def global_ref(dependency_type: TypeForm[T], /, *, cache: bool = True) -> T:
    """Create a lazy reference to a dependency of the global container."""
    return cast(T, GlobalRef(dependency_type, cache=cache))
