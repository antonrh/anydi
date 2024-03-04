"""AnyDI public objects and functions."""

from typing import Any

from ._container import Container, request, singleton, transient
from ._module import Module, provider
from ._scanner import injectable
from ._types import Marker, Provider, Scope


def dep() -> Any:
    """A marker for dependency injection."""
    return Marker()


# Alias for dependency auto marker
auto = dep


__all__ = [
    "Container",
    "Module",
    "Provider",
    "Scope",
    "auto",
    "dep",
    "injectable",
    "provider",
    "request",
    "singleton",
    "transient",
]
