"""PyxDI public objects and functions."""
from typing import Any

from ._container import Container, request, singleton, transient
from ._module import Module, provider
from ._scanner import injectable
from ._types import Marker, Provider, Scope


def auto() -> Any:
    """A marker for automatic dependency injection."""
    return Marker()


__all__ = [
    "Container",
    "Module",
    "Provider",
    "Scope",
    "auto",
    "injectable",
    "provider",
    "request",
    "singleton",
    "transient",
]
