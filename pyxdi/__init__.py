"""PyxDI public objects and functions."""
from typing import Any, cast

from ._container import Container, request, singleton, transient
from ._module import Module, provider
from ._scanner import injectable
from ._types import Marker, Provider, Scope

# Container type alias for backward compatibility
PyxDI = Container

# Dependency marker with Any type
dep = cast(Any, Marker())


__all__ = [
    "dep",
    "injectable",
    "Module",
    "provider",
    "Provider",
    "Container",
    "PyxDI",
    "Scope",
    "singleton",
    "request",
    "transient",
]
